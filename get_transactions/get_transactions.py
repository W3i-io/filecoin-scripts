#!/usr/bin/python3

import requests
import pyodbc
import configparser
import time
from datetime import datetime, timedelta
import json
import math
from colorama import Fore
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout
from json.decoder import JSONDecodeError

# Define constants
FILECOIN_GENESIS_TIMESTAMP = 1598306400
ORIGIN = datetime(1970, 1, 1, 0, 0, 0)
CONFIG_FILE_PATH = './get_transactions.conf'
PAGE_SIZE = 50

def filfox_api_call(call_type, *param):
    headers = {
        'X-API-KEY': config["filfox"]["apikey"],
        'Content-Type': 'application/json'
    }
    payload = {}

    if call_type == "get_actor_info":
        api_request = f'https://filfox.info/api/v1/address/{param[0]}'
    elif call_type == "get_tipset_info":
        api_request = f'https://filfox.info/api/v1/tipset/{param[0]}'
    elif call_type == "get_all_messages":
        api_request = f'https://filfox.info/api/v1/address/{param[0]}/messages'
    elif call_type == "get_messages_page":
        api_request = f'https://filfox.info/api/v1/address/{param[0]}/messages?pageSize={param[2]}&page={param[1]}'
    elif call_type == "get_message":
        api_request = f'https://filfox.info/api/v1/message/{param[0]}'

    retries = 5
    backoff_factor = 1
    timeout = 10  # seconds

    for attempt in range(retries):
        try:
            response = requests.get(api_request, headers=headers, data=payload, timeout=timeout)
            response.raise_for_status()
            try:
                return response.json()
            except JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                if attempt < retries - 1:
                    sleep_time = backoff_factor * (2 ** attempt)
                    print(f"Retrying in {sleep_time} seconds due to JSON error...")
                    time.sleep(sleep_time)
                else:
                    print("Maximum retries reached due to JSON decode error. Exiting.")
                    return None
        except (ChunkedEncodingError, ConnectionError, Timeout) as e:
            print(f"Error occurred: {e}")
            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt)
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print("Maximum retries reached. Exiting.")
                return None
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
            if response.status_code != 200:
                print(f"Filfox API error: {response.status_code}")
                print("Will try again in 20 seconds")
                time.sleep(20)
            else:
                return None
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            return None

def main():
    print(datetime.now(), "- Starting...")
    print(datetime.now(), "- Reading configuration file")
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)

    cnxn = pyodbc.connect(
        f'DRIVER={config["sql"]["driver"]};'
        f'SERVER=tcp:{config["sql"]["server"]};'
        f'PORT=1433;DATABASE={config["sql"]["database"]};'
        f'UID={config["sql"]["username"]};'
        f'PWD={config["sql"]["password"]}'
    )
    cursor = cnxn.cursor()

    query = "SELECT * FROM AccountsList WHERE Active=1"
    cursor.execute(query)
    accounts_list = cursor.fetchall()

    for account in accounts_list:
        print(Fore.GREEN + f"New account: {account.ActorID}")

        if account.IsMiner:
            print(Fore.YELLOW + 'Account is a miner, checking for block rewards')
            miner_info = filfox_api_call("get_actor_info", account.ActorID)
            last_seen_height = miner_info["lastSeenHeight"]
            last_epoch_check_rewards = account.LastEpochCheckRewards
            if last_seen_height > last_epoch_check_rewards:
                while last_epoch_check_rewards < last_seen_height:
                    epochs = filfox_api_call("get_tipset_info", last_epoch_check_rewards)
                    print(Fore.WHITE + str(last_epoch_check_rewards))
                    for reward in epochs["blocks"]:
                        if reward["miner"] == account.ActorID:
                            print(Fore.CYAN + f"Block reward found at height: {last_epoch_check_rewards}")
                            timestamp = ORIGIN + timedelta(seconds=(FILECOIN_GENESIS_TIMESTAMP + (last_epoch_check_rewards * 30)))
                            query = (
                                "INSERT INTO FilecoinTransactionsList "
                                "(MessageID, MessageDate, ActorID, Height, Nonce, MethodID, MethodName, ExitCode, TransferType, TransferFrom, TransferTo, TransferAmount) "
                                "VALUES "
                                f"('{reward['cid']}', '{timestamp}', '{reward['miner']}', {last_epoch_check_rewards}, 0, 14, 'AddLockedFund', 0, 'reward', 'f02', '{reward['miner']}', {reward['reward']})"
                            )
                            cursor.execute(query)
                            cnxn.commit()
                    last_epoch_check_rewards += 1
                    update_query = f"UPDATE AccountsList SET LastEpochCheckRewards={last_epoch_check_rewards} WHERE ActorID='{account.ActorID}'"
                    cursor.execute(update_query)
                    cnxn.commit()

        messages = filfox_api_call("get_all_messages", account.ActorID)
        print(Fore.WHITE + "Checking for new messages")
        if account.CheckAllMessages:
            num_processed_pages = 0
            counter = 0
        else:
            counter = account.Counter
            num_processed_pages = math.floor(counter / PAGE_SIZE)
        print(Fore.WHITE + f"Current counter value in DB: {counter}")
        print(Fore.WHITE + f"Messages total count in filfox: {messages['totalCount']}")
        if counter < messages["totalCount"]:
            print(Fore.WHITE + "Messages found, processing...")
            total_num_pages = math.ceil(messages["totalCount"] / PAGE_SIZE)
            num_pages = range(total_num_pages - num_processed_pages)
            print(Fore.WHITE + f"Total number of pages in filfox: {total_num_pages}")
            print(Fore.WHITE + f"Total already processed pages: {num_processed_pages}")
            print(Fore.WHITE + f"Number of pages to be processed: {list(num_pages)}")
            for page_number in num_pages:
                print(Fore.MAGENTA + f"Processing page: {num_processed_pages + page_number}/{total_num_pages} (Account: {account.ActorID})")
                messages_page = filfox_api_call("get_messages_page", account.ActorID, page_number, PAGE_SIZE)
                if messages_page is None:
                    print(Fore.RED + "Error fetching messages page")
                    continue
                for message in messages_page["messages"]:
                    query = f"SELECT * FROM FilecoinTransactionsList WHERE MessageID='{message['cid']}'"
                    cursor.execute(query)
                    check_message_exists = cursor.fetchone()
                    if check_message_exists is None:
                        print(Fore.YELLOW + f"Adding message to database: {account.ActorID} - {message['cid']}")
                        transaction = filfox_api_call("get_message", message["cid"])
                        if transaction is not None:
                            if "transfers" in transaction:
                                for transfer in transaction["transfers"]:
                                    if transfer["fromId"] == account.ActorID:
                                        timestamp = ORIGIN + timedelta(seconds=transaction["timestamp"])
                                        insert_query = (
                                            "INSERT INTO FilecoinTransactionsList "
                                            "(MessageID, MessageDate, ActorID, Height, Nonce, MethodID, MethodName, ExitCode, TransferType, TransferFrom, TransferTo, TransferAmount) "
                                            "VALUES "
                                            f"('{transaction['cid']}', '{timestamp}', '{account.ActorID}', {transaction['height']}, {transaction['nonce']}, {transaction['methodNumber']}, '{transaction['method']}', "
                                            f"{transaction['receipt']['exitCode']}, '{transfer['type']}', '{transfer['fromId']}', '{transfer['toId']}', -{transfer['value']})"
                                        )
                                        cursor.execute(insert_query)
                                        cnxn.commit()
                                        print(Fore.LIGHTBLUE_EX + f"Adding transaction to database: {account.ActorID} - {transaction['cid']}")
                                    elif transfer["type"] == "transfer":
                                        timestamp = ORIGIN + timedelta(seconds=transaction["timestamp"])
                                        insert_query = (
                                            "INSERT INTO FilecoinTransactionsList "
                                            "(MessageID, MessageDate, ActorID, Height, Nonce, MethodID, MethodName, ExitCode, TransferType, TransferFrom, TransferTo, TransferAmount) "
                                            "VALUES "
                                            f"('{transaction['cid']}', '{timestamp}', '{account.ActorID}', {transaction['height']}, {transaction['nonce']}, {transaction['methodNumber']}, '{transaction['method']}', "
                                            f"{transaction['receipt']['exitCode']}, '{transfer['type']}', '{transfer['fromId']}', '{transfer['toId']}', {transfer['value']})"
                                        )
                                        cursor.execute(insert_query)
                                        cnxn.commit()
                                        print(Fore.LIGHTBLUE_EX + f"Adding transaction to database: {account.ActorID} - {transaction['cid']}")
                        counter += 1
                        update_query = f"UPDATE AccountsList SET Counter={counter} WHERE ActorID='{account.ActorID}'"
                        cursor.execute(update_query)
                        cnxn.commit()
                    else:
                        print(Fore.WHITE + f"Message already exists: {message['cid']}")
                        if account.CheckAllMessages:
                            counter += 1
                            update_query = f"UPDATE AccountsList SET Counter={counter} WHERE ActorID='{account.ActorID}'"
                            cursor.execute(update_query)
                            cnxn.commit()
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
