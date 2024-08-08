#!/usr/bin/python3

import requests
import pyodbc
import configparser
import time
from datetime import datetime
from datetime import timedelta
import json
import math
import sys
from colorama import Fore
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout
from json.decoder import JSONDecodeError

# Define constants
filecoin_genesis_timestamp = 1598306400
origin = datetime(1970, 1, 1, 0, 0, 0)
configFilePath = r'./get_transactions.conf'
page_size = 50
update_count = 0

# Function to make API calls to Filfox with different call types


def filfox_api_call(call_type, *param):
    headers = {
        'X-API-KEY': config["filfox"]["apikey"],
        'Content-Type': 'application/json'
    }
    payload = {}

    if call_type == "get_actor_info":
        api_request = 'https://filfox.info/api/v1/address/' + str(param[0])
    elif call_type == "get_tipset_info":
        api_request = 'https://filfox.info/api/v1/tipset/' + str(param[0])
    elif call_type == "get_all_messages":
        api_request = 'https://filfox.info/api/v1/address/' + str(param[0]) + '/messages'
    elif call_type == "get_messages_page":
        api_request = 'https://filfox.info/api/v1/address/' + str(param[0]) + '/messages?pageSize=' + str(param[2]) + '&page=' + str(param[1])
    elif call_type == "get_message":
        api_request = 'https://filfox.info/api/v1/message/' + str(param[0])

    retries = 5
    backoff_factor = 1
    timeout = 10  # seconds

    for attempt in range(retries):
        try:
            response = requests.request("GET", api_request, headers=headers, data=payload, timeout=timeout)
            response.raise_for_status()
            try:
                return json.loads(response.text)
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
                print("Filfox API error:" + str(response.status_code))
                print("will try again in 20 seconds")
                time.sleep(20)
            else:
                return None
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            return None
        

print(datetime.now(), "- Starting...")

print(datetime.now(), "- Reading configuration file")
# Read the config file
config = configparser.ConfigParser()

config.read(configFilePath)



# Connect to the SQL database
cnxn = pyodbc.connect(
    'DRIVER=' + config["sql"]["driver"] +
    ';SERVER=tcp:' + config["sql"]["server"] +
    ';PORT=1433;DATABASE=' + config["sql"]["database"] +
    ';UID=' + config["sql"]["username"] +
    ';PWD=' + config["sql"]["password"]
)
cursor = cnxn.cursor()

# Fetch the list of active accounts from the database
query = "select * from AccountsList where Active=1"
cursor.execute(query)
accounts_list = cursor.fetchall()




# Loop through each account in the accounts list
for account in accounts_list:
    print(Fore.GREEN + "new account: " + account.ActorID)

    # If the account is a miner, check for block rewards
    if account.IsMiner == True:
        print(Fore.YELLOW + 'account is a miner, checking for block rewards')
        miner_info = filfox_api_call("get_actor_info", account.ActorID)
        last_seen_height = miner_info["lastSeenHeight"]
        last_epoch_check_rewards = account.LastEpochCheckRewards
        if last_seen_height > last_epoch_check_rewards:
            while last_epoch_check_rewards < last_seen_height:
                epochs = filfox_api_call("get_tipset_info", last_epoch_check_rewards)
                print(Fore.WHITE + str(last_epoch_check_rewards))
                for reward in epochs["blocks"]:
                    if reward["miner"] == account.ActorID:
                        print(Fore.CYAN + "block reward found at height: " + str(last_epoch_check_rewards))
                        timestamp = origin + timedelta(seconds=(filecoin_genesis_timestamp + (last_epoch_check_rewards * 30)))
                        query = (
                            "INSERT INTO FilecoinTransactionsList (MessageID,MessageDate,ActorID,Height,Nonce,MethodID,MethodName,ExitCode,TransferType,TransferFrom,TransferTo,TransferAmount) VALUES "
                            "('" + str(reward["cid"]) + "','" + str(timestamp) + "','" + str(reward["miner"]) + "'," + str(last_epoch_check_rewards) + ",0,14,'AddLockedFund'"
                            ",0,'reward','f02','" + str(reward["miner"]) + "'," + str(reward["reward"]) + ")"
                        )
                        cursor.execute(query)
                        cnxn.commit()
                last_epoch_check_rewards += 1
                update_query = "Update AccountsList set LastEpochCheckRewards=" + str(last_epoch_check_rewards) + " where ActorID='" + account.ActorID + "'"
                cursor.execute(update_query)
                cnxn.commit()

    # Fetch all messages for the account
    messages = filfox_api_call("get_all_messages", account.ActorID)
    print(Fore.WHITE + "checking for new messages")
    if account.CheckAllMessages == 1:
        num_processed_pages = 0
        counter = 0
    else:
        counter = account.Counter
        num_processed_pages = math.floor(counter / page_size)
    print(Fore.WHITE + "Current counter value in DB:" + str(counter))
    print(Fore.WHITE + "Messages total count in filfox:" + str(messages["totalCount"]))
    if counter < messages["totalCount"]:
        print(Fore.WHITE + "Messages found, processing...")
        total_num_pages = math.ceil(messages["totalCount"] / page_size)
        num_pages = range(total_num_pages - num_processed_pages)
        print(Fore.WHITE + "total number of pages in filfox: " + str(total_num_pages))
        print(Fore.WHITE + "total already processed pages: " + str(num_processed_pages))
        print(Fore.WHITE + "Number of pages to be processed: " + str(num_pages))
        # Process each page of messages
        for page_number in num_pages:
            print(Fore.MAGENTA + "processing page: " + str(num_processed_pages + page_number) + "/" + str(total_num_pages) + " (Account: " + account.ActorID + ")")
            messages = filfox_api_call("get_messages_page", account.ActorID, str(page_number), page_size)
            for message in messages["messages"]:
                query = "select * from FilecoinTransactionsList where MessageID='" + message["cid"] + "'"
                cursor.execute(query)
                check_message_exists = cursor.fetchone()
                if check_message_exists is None:
                    print(Fore.YELLOW + "adding message to database:" + account.ActorID + " - " + message["cid"])
                    transaction = filfox_api_call("get_message", message["cid"])
                    if transaction is not None:
                        if "transfers" in transaction:
                            for transfer in transaction["transfers"]:
                                if transfer["fromId"] == account.ActorID:
                                    timestamp = origin + timedelta(seconds=transaction["timestamp"])
                                    insert_query = (
                                        "INSERT INTO FilecoinTransactionsList (MessageID,MessageDate,ActorID,Height,Nonce,MethodID,MethodName,ExitCode,TransferType,TransferFrom,TransferTo,TransferAmount) VALUES "
                                        "('" + str(transaction["cid"]) + "','" + str(timestamp) + "','" + str(account.ActorID) + "'," + str(transaction["height"]) + "," + str(transaction["nonce"]) + "," + str(transaction["methodNumber"]) + ",'" + str(transaction["method"]) + "'"
                                        "," + str(transaction["receipt"]["exitCode"]) + ",'" + str(transfer["type"]) + "','" + str(transfer["fromId"]) + "','" + str(transfer["toId"]) + "',-" + str(transfer["value"]) + ")"
                                    )
                                    cursor.execute(insert_query)
                                    cnxn.commit()
                                    print(Fore.LIGHTBLUE_EX + "adding transaction to database:" + account.ActorID + " - " + transaction["cid"])
                                else:
                                    if transfer["type"] == "transfer":
                                        timestamp = origin + timedelta(seconds=transaction["timestamp"])
                                        insert_query = (
                                            "INSERT INTO FilecoinTransactionsList (MessageID,MessageDate,ActorID,Height,Nonce,MethodID,MethodName,ExitCode,TransferType,TransferFrom,TransferTo,TransferAmount) VALUES "
                                            "('" + str(transaction["cid"]) + "','" + str(timestamp) + "','" + str(account.ActorID) + "'," + str(transaction["height"]) + "," + str(transaction["nonce"]) + "," + str(transaction["methodNumber"]) + ",'" + str(transaction["method"]) + "'"
                                            "," + str(transaction["receipt"]["exitCode"]) + ",'" + str(transfer["type"]) + "','" + str(transfer["fromId"]) + "','" + str(transfer["toId"]) + "'," + str(transfer["value"]) + ")"
                                        )
                                        cursor.execute(insert_query)
                                        cnxn.commit()
                                        print(Fore.LIGHTBLUE_EX + "adding transaction to database:" + account.ActorID + " - " + transaction["cid"])
                    counter += 1
                    update_query = "Update AccountsList set Counter=" + str(counter) + " where ActorID='" + str(account.ActorID) + "'"
                    cursor.execute(update_query)
                    cnxn.commit()
                else:
                    print(Fore.WHITE + "Message already exists: " + message["cid"])
                    if account.CheckAllMessages == 1:
                        counter += 1
                        update_query = "Update AccountsList set Counter=" + str(counter) + " where ActorID='" + str(account.ActorID) + "'"
                        cursor.execute(update_query)
                        cnxn.commit()
        # time.sleep(0.2)
    else:
        time.sleep(1)
