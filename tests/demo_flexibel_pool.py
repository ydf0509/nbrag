

import asyncio

from flexible_thread_pool import FlexibleThreadPool
import time



pool = FlexibleThreadPool(max_workers=100)
loop = asyncio.get_event_loop()

def f1(x):
    time.sleep(1)
    return x * 2
    
async def aio_main():
    result = await loop.run_in_executor(pool, f1, 1)
    print(f"result: {result}")
    

if __name__ == "__main__":
    loop.run_until_complete(aio_main())
   