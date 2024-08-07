#!/usr/bin/python3

import requests
import pyodbc
import time
import json
import configparser

from datetime import datetime, timedelta


# read the config file
config = configparser.ConfigParser()
configFilePath = r'./get_rewards.conf'
config.read(configFilePath)


check_date = datetime.now()
check_date -= timedelta(days=2)

cnxn = pyodbc.connect('DRIVER='+config["sql"]["driver"]+';SERVER=tcp:'+config["sql"]["server"]+';PORT=1433;DATABASE='+config["sql"]["database"]+';UID='+config["sql"]["username"]+';PWD='+config["sql"]["password"])
cursor = cnxn.cursor()

url = "https://api.spacescope.io/v2/economics/block_reward?end_date="+check_date.strftime('%Y-%m-%d')+"&start_date="+check_date.strftime('%Y-%m-%d')

payload={}
headers = {
  'authorization': 'Bearer '+config["spacescope"]["apikey"]
}

response = requests.request("GET", url, headers=headers, data=payload)

data = json.loads(response.text)

print(data)

query = "SELECT * FROM BlockRewards WHERE RewardDate='"+str(data['data'][0]['stat_date'])+"'"
result = cursor.execute(query)
row = cursor.fetchone()

if row is None:
    insert_query = "INSERT INTO BlockRewards VALUES('"+str(data['data'][0]['stat_date'])+"',"+str(data['data'][0]['reward_per_wincount'])+")"
    #cursor.execute(insert_query)
    #cnxn.commit()

cursor.close()
cnxn.close()