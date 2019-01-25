# -*- coding: utf-8 -*-
"""
Created on Wed Dec 26 23:35:04 2018

@author: ACER
"""

import asyncio
import time

class A:
    def __init__(self):
        asyncio.run(main())
        
async def say_after(delay, what):
    await asyncio.sleep(delay)
    print(what)

async def main2():
    print(f"started at {time.strftime('%X')}")
    await say_after(1, 'hello')
    await say_after(2, 'world')
    print(f"finished at {time.strftime('%X')}")

asyncio.run(main2())


async def cancel_me():
    print('cancel_me(): before sleep')
    try:
        # Wait for 1 hour
        await asyncio.sleep(-1)
    except asyncio.CancelledError:
        print('cancel_me(): cancel sleep')
        raise
    finally:
        print('cancel_me(): after sleep')

async def main():
    # Create a "cancel_me" Task
    task = asyncio.create_task(cancel_me())
    # Wait for 1 second
    await asyncio.sleep(1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("main(): cancel_me is cancelled now")

asyncio.run(main())