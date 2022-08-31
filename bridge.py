import requests
import json, os
import time
import argparse
import logging
import clientData as cd

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-i', '--interval', action="store", required=False, type=int, default=1, help="The amount of seconds with which to check if there's new prompts to generate")
arg_parser.add_argument('-u', '--username', action="store", required=False, type=str, default='Anonymous', help="The username of the owner of the KAI instance. Used to track contributions.")
arg_parser.add_argument('-p', '--password', action="store", required=False, type=str, default='Password', help="The password to make sure nobody spoofs your server instance.")
arg_parser.add_argument('-n', '--kai_name', action="store", required=False, type=str, default='My Awsome Instance', help="The server name. It will be shown to the world and there can be only one.")
arg_parser.add_argument('-k', '--kai_url', action="store", required=False, type=str, default='http://localhost:5000', help="The KoboldAI server URL. Where the bridge will get its generations from.")
arg_parser.add_argument('-c', '--cluster_url', action="store", required=False, type=str, default='http://dbzer0.com:5001', help="The KoboldAI Cluster URL. Where the bridge will pickup prompts and send the finished generations.")

model = ''
max_content_length = 1024
max_length = 80

def validate_kai(kai):
    global model
    global max_content_length
    global max_length
    try:
        model_req = requests.get(kai + '/api/latest/model')
        if type(model_req.json()) is not dict:
            logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
            return(False)
        model = model_req.json()["result"]
    except requests.exceptions.JSONDecodeError:
        logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
        return(False)
    except requests.exceptions.ConnectionError:
        logging.error(f"Server {kai} is not reachable. Are you sure it's running?")
        return(False)
    try:
        model_req = requests.get(kai + '/api/latest/config/max_context_length')
        if type(model_req.json()) is not dict:
            logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
            return(False)
        max_content_length = model_req.json()["value"]
    except requests.exceptions.JSONDecodeError:
        logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
        return(False)
    try:
        model_req = requests.get(kai + '/api/latest/config/max_length')
        if type(model_req.json()) is not dict:
            logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
            return(False)
        max_length = model_req.json()["value"]
    except requests.exceptions.JSONDecodeError:
        logging.error(f"Server {kai} is up but does not appear to be a KoboldAI server. Are you sure it's running the UNITED branch?")
        return(False)
    return(True)


if __name__ == "__main__":
    #logging.basicConfig(filename='server.log', encoding='utf-8', level=logging.DEBUG)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',level=logging.DEBUG)
    args = arg_parser.parse_args()
    global interval
    interval = args.interval
    current_id = None
    current_payload = None
    loop_retry = 0
    username = args.username if args.username else cd.username
    password = args.password if args.password else cd.password
    kai_name = args.kai_name if args.kai_name else cd.kai_name
    kai_url = args.kai_url if args.kai_url else cd.kai_url
    cluster = args.cluster_url if args.cluster_url else cd.cluster_url
    while True:
        if not validate_kai(kai_url):
            logging.warning(f"Waiting 10 seconds...")
            time.sleep(10)
            continue
        gen_dict = {
            "username": username,
            "password": password,
            "name": kai_name,
            "model": model,
            "max_length": max_length,
            "max_content_length": max_content_length,
        }
        if current_id:
            loop_retry += 1
        else:
            try:
                pop_req = requests.post(cluster + '/generate/pop', json = gen_dict)
            except requests.exceptions.ConnectionError:
                logging.warning(f"Server {cluster} unavailable during pop. Waiting 10 seconds...")
                time.sleep(10)
                continue
            if not pop_req.ok:
                logging.warning(f"During gen pop, server {cluster} responded: {pop_req.text}. Waiting for 10 seconds...")
                time.sleep(10)
                continue
            pop = pop_req.json()
            if not pop["id"]:
                logging.info(f"Server {cluster} has no valid generations to do for us. Skipped Info: {pop['skipped']}.")
                time.sleep(interval)
                continue
            current_id = pop['id']
            current_payload = pop['payload']
        gen_req = requests.post(kai_url + '/api/latest/generate/', json = current_payload)
        if type(gen_req.json()) is not dict:
            logging.error(f'KAI instance {kai_instance} API unexpected response on generate: {gen_req}. Sleeping 10 seconds...')
            time.sleep(9)
            continue
        if gen_req.status_code == 503:
            logging.info(f'KAI instance {kai_instance} Busy (attempt {loop_retry}). Will try again...')
            continue
        current_generation = gen_req.json()["results"][0]["text"]
        submit_dict = {
            "id": current_id,
            "generation": current_generation,
            "password": password,
        }
        while current_id and current_generation:
            try:
                submit_req = requests.post(cluster + '/generate/submit', json = submit_dict)
                if submit_req.status_code == 404:
                    logging.warning(f"The generation we were working on got stale. Aborting!")
                elif not submit_req.ok:
                    logging.error(submit_req.status_code)
                    logging.warning(f"During gen submit, server {cluster} responded: {submit_req.text}. Waiting for 10 seconds...")
                    time.sleep(10)
                    continue
                else:
                    logging.info(f'Submitted generation with id {current_id} and contributed for {submit_req.json()["reward"]}')
                current_id = None
                current_payload = None
                current_generation = None
            except requests.exceptions.ConnectionError:
                logging.warning(f"Server {cluster} unavailable during submit. Waiting 10 seconds...")
                time.sleep(10)
                continue
        time.sleep(interval)
