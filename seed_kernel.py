import redis
import time

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

print("[BOOTSTRAP] Injecting core truth nodes into AROM Ephemeral Grid...")

# 1. Physics Constant
r.hset("truth:speed of light", mapping={
    "value": "299, 792, 458 m/s",
    "context": "The speed of light in vacuum is a universal physical constant exactly equal to 299 792 458 m/s.",
    "timestamp": time.time()
})

# 2. Semantic Fact
r.hset("truth:capital of france", mapping={
    "value": "Paris",
    "context": "Paris is the capital and most populous city of France.",
    "timestamp": time.time()
})

print("[BOOTSTRAP] Success! Core nodes locked into RAM.")