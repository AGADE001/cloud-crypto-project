import asyncio
import os
import aiohttp
import asyncpg
import redis.asyncio as aioredis
from dotenv import load_dotenv

#-------------------------------------------#
load_dotenv()#looks for env file and storing it into a variable
#Constant variables
COINGECKO_API_KEY   = os.getenv('COINGECKO_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DB_USER             = os.getenv('DB_USER')
DB_PASSWORD         = os.getenv('DB_PASSWORD')
DB_NAME             = os.getenv('DB_NAME')
DB_HOST             = os.getenv('DB_HOST')
DIGITAL_COMMODITIES = [
    "bitcoin", "ethereum", "solana", "ripple", 
    "cardano", "chainlink", "avalanche", "polkadot", 
    "stellar", "hedera", "litecoin", "dogecoin", 
    "shiba-inu", "tezos", "bitcoin-cash", "aptos"
    ]
#-------------------------------------------#

#--------------Database Function--------------#
async def postgres_db(crypto_name, current_price, sma_value, deviation_percent): #This function gets triggered by analytics_and_alert():
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=5432
        ) 
        query = """
                INSERT INTO price_logs (crypto_name, current_price, sma_value, deviation_percent)
                VALUES ($1,$2,$3,$4)
            """
        await conn.execute(query, crypto_name, current_price, sma_value, deviation_percent)
    except Exception as e:
        print(f"[PostgreDB] Failed Connection to Database: {e}")
#-------------------------------------------#       

#----------Discord Alerting Function----------#
async def send_discord_alert(crypto_name, current_price, last_price, sma_value, deviation_percent):
    if not DISCORD_WEBHOOK_URL:
        print("[Discord_Webhook] Error: URL cannot be found in ENV file.")
        return
    # Discord webhooks expect a payload containing a 'content' field or an embed structure
    payload = {
        "content" : f""" 🚨Threshold Breach Alert🚨\n
                    Asset:         {crypto_name.upper()}\n
                    Price:         {current_price} from {last_price}\n
                    10-Period SMA: {sma_value}\n
                    Deviation:     {deviation_percent}% from moving average 
                    """
    }
    print(f"[Discord_Webhook] Dispatching payload to network for {crypto_name.upper()} ")

    try:
        async with aiohttp.ClientSession() as alert_session: #Inititializes new network session to connect to discord
            async with alert_session.post(url=DISCORD_WEBHOOK_URL, json=payload) as post_response: #uses url and payload to make post request to Discord webhook
                if post_response.status in (200,204):
                    print(f"[Webhook Worker] Post request to Discord API accepted (Status:{post_response.status})")
                else:
                    print(f"[Webhook Worker] Post request failed (Status: {post_response.status})")
    except Exception as e:
        print(f"[Webhook Worker] Unable to connect with Discord during broadcast(ErrorCode: {e})")
#-------------------------------------------#

#---------Analytics // Calculations---------#
async def analytics_and_alert(redis, asset_list): #This function gets triggered within data_fetcher():
    await asyncio.sleep(1)

    for crypto_name in asset_list:
        list_key = f"{crypto_name}_price_history"
        latest_prices = await redis.lrange(list_key,-10,-1)

        if not latest_prices:
            continue

        #-----Math-----#
        prices_as_float = [float(p) for p in latest_prices] #makes every price convert from string to float
        sma_value = sum(prices_as_float) / len(latest_prices)
        # print(prices_as_float)
        # print(sma_value)
        sma_value = round(sma_value,4)

        sma_redis_key = f"{crypto_name}_sma_10"
        await redis.set(sma_redis_key, sma_value)

        if len(prices_as_float) > 1:
            last_price = prices_as_float[-2]
        current_price = prices_as_float[-1]

        if sma_value > 0:
            #Checks if SMA strays too far from baseline, here being 5%
            deviation = abs(current_price - sma_value) / sma_value
            deviation_percent = round(deviation * 100, 2)
            if len(latest_prices) == 10:
                await postgres_db(crypto_name, current_price, sma_value, deviation_percent)#Saves info into database
            if deviation > 0.05:
                print(f"Threshold Breach [!!!]: {crypto_name.upper()} deviated by {deviation_percent} from SMA")
                await send_discord_alert(crypto_name, current_price, last_price, sma_value, deviation_percent) #Triggers function to send SMA deviation of 5% to discord server
        print(f"Asset: [{crypto_name.upper()}] Current: [${current_price}] 10-Period SMA: [{sma_value}] Window Count: [{len(latest_prices)}]")
#-------------------------------------------#

#----------Data Retrieval Function----------#
async def data_fetcher(redis, asset_list):
    asset_ids = (",").join(asset_list)#joins the list of commodities into a string for payload

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={asset_ids}&vs_currencies=usd"

    headers = {
        "accept":"application/json",
        "x-cg-demo-api-key":COINGECKO_API_KEY
    }
    #-----Internet Communication-----#
    async with aiohttp.ClientSession() as session: #Initializing active network session client
        while True:
            print("----------------------------- New Request -----------------------------")
            print("[Data_Fetcher] sending HTTP batch request to CoinGecko")
            try:
                async with session.get(url=url, headers=headers) as response: #Sending request to url with initialized client
                    if response.status == 200: #If the connection was successful do this:
                        market_data = await response.json() #need to use 'await' here to extraxt from async function
                        for crypto_name, price_info in market_data.items():
                            price = price_info["usd"]
                            #-----Redis-----#
                            await redis.set(f"{crypto_name}_current_price", price)#Writes to redis (key,value)

                            list_key = f"{crypto_name}_price_history"
                            await redis.rpush(list_key, price) #appends latest price of given asset to end of list // and creates new list if not exisiting 
                            await redis.ltrim(list_key, -10, -1) #keeps last 10 appended and removes any old record
                        print("[Data_Fetcher] Appended new batch into Redis Cache. Sleeping 15s")
                        await analytics_and_alert(redis, asset_list)
                    else:
                        print(f"[Data_Fetcher] Network connection failed, Error Code: {response.status}")
            except Exception as e:
                print(f"[Data_Fetcher] Exception: {e}")
            await asyncio.sleep(15)
#-------------------------------------------#

#----------Start of Code----------#
async def main():
    print("Connecting to Redis Cache Service on internal network...")
    redis_client = aioredis.from_url("redis://crypto_redis:6379", decode_responses = True)#Initializing redis connection
    await data_fetcher(redis_client, DIGITAL_COMMODITIES)
#---------------------------------#
if __name__ == '__main__': 
    asyncio.run(main())
#Ignition