import discord
from discord.ext import commands
import requests  # For making HTTP requests to Ollama API

MODEL = 'llama3.2:1b'

# Replace 'YOUR_BOT_TOKEN' with your bot's token
TOKEN = ''

# Ollama API URL
OLLAMA_API_URL = 'http://localhost:11434/api/chat'

# Initialize the bot with command prefix and intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store the thread ID to monitor
monitored_threads = {}

# Command to start monitoring a thread
@bot.command()
async def monitor_thread(ctx):
    if isinstance(ctx.channel, discord.Thread):
        thread_id = ctx.channel.id
        monitored_threads[thread_id] = True
        await ctx.send(f"Monitoring thread {thread_id}.")
    else:
        await ctx.send("This command can only be run in a thread.")

# Event listener for when the bot has switched from offline to online.
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Event listener for when a new message is sent
@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Check if the message is in a monitored thread
    if message.channel.id in monitored_threads:
        thread_id = message.channel.id
        thread = bot.get_channel(thread_id)
        if thread is None or not isinstance(thread, discord.Thread):
            monitored_threads.pop(thread_id, None)
            print(f"Thread {thread_id} no longer exists. Stopped monitoring.")
            return

        try:
            # Fetch the last 50 messages from the thread in chronological order
            messages = []
            async for msg in thread.history(limit=50, oldest_first=True):
                messages.append(msg)

            # Print the messages in the order they are fetched for debugging
            print("Fetched Messages in Chronological Order:")
            for msg in messages:
                print(f"{msg.created_at} - {msg.author.name}: {msg.content}")

            # Tag messages as sent by the bot or the user
            tagged_messages = []
            for msg in messages:
                if msg.author == bot.user:
                    tagged_messages.append({"role": "assistant", "content": msg.content})
                else:
                    tagged_messages.append({"role": "user", "content": msg.content})

            # Print the tagged messages for debugging
            print("Tagged Messages:")
            for msg in tagged_messages:
                print(msg)

            # Create the payload with the required fields
            payload = {
                "model": MODEL,
                "messages": tagged_messages,
                "stream": False  # Ensure this is a boolean
            }

            # Print the payload for debugging
            print("Payload to Ollama API:")
            print(payload)

            # Send the tagged conversation to the Ollama API
            response = await send_to_ollama(payload)

            # Send the LLM response back to the thread
            if response:
                # Check if the response is too long and split it if necessary
                if len(response) > 2000:
                    # Split the response into chunks of 2000 characters or less
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await thread.send(chunk)
                else:
                    await thread.send(response)
            else:
                await thread.send("Failed to get a response from the LLM.")

        except discord.Forbidden:
            await message.channel.send("I don't have permission to read messages in this thread.")
        except discord.HTTPException as e:
            await message.channel.send(f"An error occurred while fetching messages: {e}")

    # Ensure the bot processes commands
    await bot.process_commands(message)

# Function to send tagged conversation to Ollama API
async def send_to_ollama(payload):
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()  # Raise an error for bad responses

        # Print the response for debugging
        print("API Response:")
        print(response.json())

        # Extract the response from the API
        response_data = response.json()
        if  'message' in response_data and 'content' in response_data['message']:
            return response_data['message']['content']
        else:
            print("Response does not contain the expected structure:")
            print(response_data)
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error sending messages to Ollama API: {e}")
        if response.status_code == 404:
            print(f"Endpoint not found: {response.url}")
        elif response.status_code == 400:
            print(f"Bad Request: {response.text}")
        return None

# Run the bot with the token
bot.run(TOKEN)