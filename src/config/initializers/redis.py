import redis.asyncio
import redis

from os import getenv
from dotenv import load_dotenv

load_dotenv()

REDIS_CLIENT = redis.Redis(
	host=str(getenv('REDIS_HOST')), 
	port=int(getenv('REDIS_PORT')), 
	db=int(getenv('REDIS_DB'))
)

REDIS_CLIENT_ASYNCIO = redis.asyncio.Redis(
	host=str(getenv('REDIS_HOST')), 
	port=int(getenv('REDIS_PORT')), 
	db=int(getenv('REDIS_DB'))
)
