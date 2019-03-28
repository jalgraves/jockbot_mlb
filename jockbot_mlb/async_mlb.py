import asyncio

queue = asyncio.Queue()


async def foo():
    await asyncio.sleep(2)
    print("fu ahole")
    return "fuck you"


async def bar():
    await asyncio.sleep(2)
    print("blah")
    return "eat shit"


async def work():
    while True:
        task = await queue.get()
        if not task:
            print("No F'n task")
            break

        result = await task()
        print(result)
        if queue.empty():
            print('fofdij')
            break


async def fuck():
    await queue.join()
    return


queue.put_nowait(foo)
queue.put_nowait(bar)

loop = asyncio.get_event_loop()
loop.run_until_complete(work())
loop.close()
def __repr__(self):
        message = [
            f"Team: {self.name}",
            f"Current Season: {self.current_season}",
            f"Games Played: {len(self.played_games)}",
            f"Games Remaining: {len(self.remaining_games)}"
        ]
        return "\n".join(message)