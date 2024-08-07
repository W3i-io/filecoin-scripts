#!/usr/bin/python3

import requests
import pyodbc
import time
import json
import configparser
from datetime import datetime, timedelta

# Read the configuration file
config = configparser.ConfigParser()
configFilePath = r'./get_rewards.conf'
config.read(configFilePath)

# Set the check date to 2 days ago from now
check_date = datetime.now()
check_date -= timedelta(days=2)

# Connect to the SQL database using credentials from the config file
cnxn = pyodbc.connect(
    'DRIVER=' + config["sql"]["driver"] + 
    ';SERVER=tcp:' + config["sql"]["server"] + 
    ';PORT=1433;DATABASE=' + config["sql"]["database"] + 
    ';UID=' + config["sql"]["username"] + 
    ';PWD=' + config["sql"]["password"]
)
cursor = cnxn.cursor()

# Create the API request URL with the check date
url = (
    "https://api.spacescope.io/v2/economics/block_reward?"
    "end_date=" + check_date.strftime('%Y-%m-%d') + 
    "&start_date=" + check_date.strftime('%Y-%m-%d')
)

# Set the request headers with the API key from the config file
payload = {}
headers = {
    'authorization': 'Bearer ' + config["spacescope"]["apikey"]
}

# Send a GET request to the API
response = requests.request("GET", url, headers=headers, data=payload)

# Parse the JSON response
data = json.loads(response.text)

# Print the received data for debugging purposes
print(data)

# Query to check if the reward for the specific date already exists in the database
query = (
    "SELECT * FROM BlockRewards WHERE RewardDate='" +
    str(data['data'][0]['stat_date']) + "'"
)
result = cursor.execute(query)
row = cursor.fetchone()

# If the row doesn't exist, insert the new reward data into the database
if row is None:
    insert_query = (
        "INSERT INTO BlockRewards VALUES('" +
        str(data['data'][0]['stat_date']) + "'," +
        str(data['data'][0]['reward_per_wincount']) + ")"
    )
    cursor.execute(insert_query)
    cnxn.commit()

# Close the cursor and the database connection
cursor.close()
cnxn.close()
