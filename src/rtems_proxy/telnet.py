import asyncio
import signal
from time import sleep

import telnetlib3


class TelnetRTEMS:
    def __init__(self, hostname: str, port: int, reboot: bool, pause: bool):
        self.hostname = hostname
        self.port = port
        self.reboot = reboot
        self.pause = pause
        self.running = True
        self.terminated = False
        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)

    def terminate(self, *args):
        self.running = False
        self.terminated = True

    async def user_input(self, writer):
        loop = asyncio.events._get_running_loop()

        while self.running:
            # run the wait for input in a separate thread
            cmd = await loop.run_in_executor(None, input)
            # look for control + ] to terminate the session
            if b"\x1d" in cmd.encode():
                self.running = False
                break
            writer.write(cmd)
            writer.write("\r")
        writer.close()

    async def server_output(self, reader):
        while self.running:
            out_p = await reader.read(1024)
            if not out_p:
                raise EOFError("Connection closed by server")
            print(out_p, flush=True, end="")
        reader.close()

    async def shell(self, reader, writer):
        # user input and server output in separate tasks
        tasks = [
            self.server_output(reader),
            self.user_input(writer),
        ]

        await asyncio.gather(*tasks)

    async def send_command(self, cmd):
        reader, writer = await telnetlib3.open_connection(self.hostname, self.port)

        writer.write("\r")
        await asyncio.sleep(0.1)
        prompt = await reader.read(1024)
        print(f"prompt is {prompt.strip()}")

        print(f"Sending command: {cmd}")
        writer.write(f"{cmd}\r")
        await asyncio.sleep(0.1)
        result = await reader.read(1024)
        print(f"Result is: {result.strip()}")

        reader.close()
        writer.close()

    async def connect(self):
        while True:  # retry loop
            try:
                if self.reboot:
                    print("REBOOTING IOC ...")
                    await self.send_command("exit")
                    self.reboot = False  # only reboot once
                elif self.pause:
                    print("Un-stopping IOC")
                    await self.send_command("iocRun")

                # start interactive session
                reader, writer = await telnetlib3.open_connection(
                    self.hostname, self.port, shell=self.shell
                )
                await writer.protocol.waiter_closed

                if self.terminated and self.pause:
                    print("Stopping IOC")
                    await self.send_command("iocPause")

                break  # interactive session done so exit retry loop

            except ConnectionResetError:
                # probably the previous pod is terminating and is still connected
                print("Waiting for Telnet Port (connection reset), RETRYING ...")
                sleep(3)


def connect(host_and_port: str, reboot: bool = False, pause: bool = False):
    hostname, port = host_and_port.split(":")
    telnet = TelnetRTEMS(hostname, int(port), reboot, pause)
    asyncio.run(telnet.connect())
