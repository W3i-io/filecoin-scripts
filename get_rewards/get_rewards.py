#!/usr/bin/python3

import requests
import pyodbc
import time
import json
import configparser
from datetime import datetime, timedelta

def read_config(config_file_path):
    config = configparser.ConfigParser()
    config.read(config_file_path)
    return config

def get_check_date(days_ago=2):
    return datetime.now() - timedelta(days=days_ago)

def connect_to_db(config):
    return pyodbc.connect(
        f'DRIVER={config["sql"]["driver"]};'
        f'SERVER=tcp:{config["sql"]["server"]};'
        f'PORT=1433;DATABASE={config["sql"]["database"]};'
        f'UID={config["sql"]["username"]};'
        f'PWD={config["sql"]["password"]}'
    )

def fetch_block_rewards(check_date, config):
    url = (
        "https://api.spacescope.io/v2/economics/block_reward?"
        f"end_date={check_date.strftime('%Y-%m-%d')}&start_date={check_date.strftime('%Y-%m-%d')}"
    )
    headers = {
        'authorization': f'Bearer {config["spacescope"]["apikey"]}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def reward_exists(cursor, reward_date):
    query = "SELECT * FROM BlockRewards WHERE RewardDate=?"
    cursor.execute(query, reward_date)
    return cursor.fetchone() is not None

def insert_reward(cursor, reward_date, reward_per_wincount):
    query = "INSERT INTO BlockRewards (RewardDate, BlockReward) VALUES (?, ?)"
    cursor.execute(query, reward_date, reward_per_wincount)

def main():
    config_file_path = './get_rewards.conf'
    config = read_config(config_file_path)
    check_date = get_check_date()
    
    cnxn = connect_to_db(config)
    cursor = cnxn.cursor()

    try:
        data = fetch_block_rewards(check_date, config)
        reward_date = data['data'][0]['stat_date']
        reward_per_wincount = data['data'][0]['reward_per_wincount']
        
        if not reward_exists(cursor, reward_date):
            insert_reward(cursor, reward_date, reward_per_wincount)
            cnxn.commit()
        else:
            print(f"Reward for {reward_date} already exists in the database.")
    finally:
        cursor.close()
        cnxn.close()

if __name__ == "__main__":
    main()
