import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import cloudscraper
import re
import mysql.connector
import configparser


# Загрузка параметров из файла конфигурации
config = configparser.ConfigParser()
config.read('config.ini')

database_host = config['DATABASE']['host']
database_user = config['DATABASE']['user']
database_password = config['DATABASE']['password']
database_name = config['DATABASE']['database']

etherscan_api_key = config['API']['etherscan_api_key']





mydb = mysql.connector.connect(
  host=database_host,
  user=database_user,
  password=database_password,
  database=database_name
)

cursor = mydb.cursor()




scraper = cloudscraper.create_scraper(delay=10, browser="chrome")

# Открываем браузер и переходим на страницу
driver = webdriver.Chrome()  # здесь используется браузер Google Chrome
driver.get('https://opensea.io/assets')

i = 1
while True:
    xpath = '//*[@id="main"]/div/div/div/div/div[3]/div[3]/div[2]/div/div[' + str(i) + ']/article/a'
    link_element = driver.find_element(By.XPATH, xpath)
    link = link_element.get_attribute('href')


    # Делаем GET-запрос на страницу
    response = scraper.get(link)
    soup = BeautifulSoup(response.content, 'lxml')

    # Ищем ссылку по заданному XPath-выражению
    link_element2 = soup.find('a', {'class': 'sc-1f719d57-0 hoTuIF sc-29427738-0 ikrGyo AccountLink--ellipsis-overflow'})
    accountlink = "https://opensea.io" + link_element2.get("href")
    linkofaccount = link_element2.get("href")

    # Парсим отсюда всю инфу про аккаунт
    responseaccount = scraper.get(accountlink)
    soupaccount = BeautifulSoup(responseaccount.content, 'lxml')

    accountinformation = soupaccount.find('script', string=lambda t: t and "window.__wired__=" in t)

    text = accountinformation.text



    # Extract address value
    address_match = re.search(r'"address":"(0x\w+)"', text)
    address = address_match.group(1) if address_match else None

    # Extract connected Instagram username
    instagram_match = re.search(r'"connectedInstagramUsername":"([^"]+)"', text)
    instagram_username = instagram_match.group(1) if instagram_match else None

    # Extract connected Twitter username
    twitter_match = re.search(r'"connectedTwitterUsername":"([^"]+)"', text)
    twitter_username = twitter_match.group(1) if twitter_match else None


    # Запрос к API etherscan.io для получения состояния адреса в $
    etherscan_api_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={etherscan_api_key}"
    response = requests.get(etherscan_api_url)

    if response.status_code == 200:
        balance_in_wei = int(response.json()["result"])
        balance_in_eth = balance_in_wei / 10 ** 18
        usd_price_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        response = requests.get(usd_price_url)
        if response.status_code == 200:
            usd_price = response.json()["ethereum"]["usd"]
            balance_in_usd = balance_in_eth * usd_price
            #print(f"Balance of address {address} is {balance_in_usd:.2f} USD")
        else:
            print("Error: unable to get Ethereum price in USD")
    else:
        print("Error: unable to get Ethereum balance for the address")


    try:
        sql= "INSERT INTO PARSED (link, wallet, balance, source, twitter, instagram) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (linkofaccount, address, round(balance_in_usd, 2), "Opensea", twitter_username, instagram_username)
        cursor.execute(sql, val)
        mydb.commit()
    except mysql.connector.IntegrityError:
        pass



    i += 1
    driver.execute_script("window.scrollBy(0, 300);")
    time.sleep(3)

cursor.close()
mydb.close()


