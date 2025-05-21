import pytchat
from openai import OpenAI
import json
import time
import requests
from pydub import AudioSegment
from pydub.playback import play
import io
import pyttsx3
import argparse
from pytchat import LiveChat, SpeedCalculator
import threading
import sys

# Глобальные заглушки для классов
class OAI:
    key = None
    model = None
    prompt = None
    temperature = None
    max_tokens = None
    top_p = None
    frequency_penalty = None
    presence_penalty = None

class EL:
    key = None
    voice = None

class LOCAL_LLM:
    localflag = None
    ip_port = None
    key_local = None

client = None
engine = None
video_id = None
tts_type = None
tts_thread = None
tts_stop_event = threading.Event()
scene_status = "Монолог"
game_status = "Выключена"
viewers_count = 0
stream_status = "Игра: " + game_status + "; Сцена: " + scene_status + "; Зрители: " + str(viewers_count)




def initTTS():
    global engine
    engine = pyttsx3.init()
    engine.setProperty('rate', 180)
    engine.setProperty('volume', 1)
    voice = engine.getProperty('voices')
    engine.setProperty('voice', voice[109].id)


def initVar():
    global video_id, tts_type

    try:
        with open("config.json", "r") as json_file:
            data = json.load(json_file)
    except:
        print("Unable to open JSON file.")
        exit()

    OAI.key = data["keys"][0]["OAI_key"]
    OAI.model = data["OAI_data"][0]["model"]
    OAI.prompt = data["OAI_data"][0]["prompt"]
    OAI.temperature = data["OAI_data"][0]["temperature"]
    OAI.max_tokens = data["OAI_data"][0]["max_tokens"]
    OAI.top_p = data["OAI_data"][0]["top_p"]
    OAI.frequency_penalty = data["OAI_data"][0]["frequency_penalty"]
    OAI.presence_penalty = data["OAI_data"][0]["presence_penalty"]

    EL.key = data["keys"][0]["EL_key"]
    EL.voice = data["EL_data"][0]["voice"]

    LOCAL_LLM.localflag = data["LOCAL_LLM"][0]["local"]
    LOCAL_LLM.ip_port = data["LOCAL_LLM"][0]["ip_port"]
    LOCAL_LLM.key_local = data["LOCAL_LLM"][0]["key"]

    tts_list = ["pyttsx3", "EL"]

    parser = argparse.ArgumentParser()
    parser.add_argument("-id", "--video_id", type=str)
    parser.add_argument("-tts", "--tts_type", default="pyttsx3", choices=tts_list, type=str)
    args = parser.parse_args()

    video_id = args.video_id
    tts_type = args.tts_type

    if tts_type == "pyttsx3":
        initTTS()


def Controller_TTS(message):
    if tts_type == "EL":
        EL_TTS(message)
    elif tts_type == "pyttsx3":
        pyttsx3_TTS(message)


def pyttsx3_TTS(message):
    global tts_thread, tts_stop_event

    def speak():
        try:
            engine.say(message)
            engine.runAndWait()
        except Exception as e:
            print(f"[TTS ERROR] {e}")

    # Если уже что-то говорит — прерываем
    if tts_thread and tts_thread.is_alive():
        tts_stop_event.set()
        engine.stop()
        tts_thread.join(timeout=1)

    tts_stop_event.clear()
    tts_thread = threading.Thread(target=speak, daemon=True)
    tts_thread.start()



def EL_TTS(message):
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{EL.voice}'
    headers = {
        'accept': 'audio/mpeg',
        'xi-api-key': EL.key,
        'Content-Type': 'application/json'
    }
    data = {
        'text': message,
        'voice_settings': {
            'stability': 0.75,
            'similarity_boost': 0.75
        }
    }
    response = requests.post(url, headers=headers, json=data, stream=True)
    audio_content = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
    play(audio_content)


def read_chat():
    try:
        chat = pytchat.create(video_id=video_id)
        schat = pytchat.create(video_id=video_id, processor=SpeedCalculator(capacity=20))

        while chat.is_alive():
            for c in chat.get().sync_items():
                print(f"\n{c.datetime} [{c.author.name}]- {c.message}\n")
                message = c.message

                response = llm(message)
                print(response)
                Controller_TTS(response)

                if schat.get() >= 20:
                    chat.terminate()
                    schat.terminate()
                    return

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[INFO] Выход из read_chat() по Ctrl+C")
        chat.terminate()
        schat.terminate()
        raise  # проброс наверх



def llm(message):
    global client
    start_sequence = " #########"
    response = client.completions.create(
        model=OAI.model,
        prompt=OAM.promt+"\n\n#########\n" + stream_status + "\n\n#########\n" + message + "\n#########\n",
        temperature=OAI.temperature,
        max_tokens=OAI.max_tokens,
        top_p=OAI.top_p,
        frequency_penalty=OAI.frequency_penalty,
        presence_penalty=OAI.presence_penalty
    )

    return response.choices[0].text


if __name__ == "__main__":
    try:
        initVar()

        # Создаём клиент после загрузки инита чтобы успеть прочитать конфиг
        if LOCAL_LLM.localflag == "yes":
            client = OpenAI(
                base_url=LOCAL_LLM.ip_port, #ip и порт, ну или домен.
                api_key=LOCAL_LLM.key_local #ключ. без него не взлетит.
            )
        else:
            client = OpenAI(api_key=OAI.key) #ключ от openai если вы мажор Ж)

        print("\nRunning!\n\n")

        while True:
            read_chat()
            print("\n\nReset!\n\n") #итерация прошла, самое время поспать)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Программа остановлена пользователем (Ctrl+C)")

        if tts_thread and tts_thread.is_alive():
            print("[INFO] Прерываю воспроизведение речи...")
            tts_stop_event.set()
            engine.stop()
            tts_thread.join(timeout=1)

        sys.exit(0)


    except EOFError:
        print("\n[INFO] Получен EOF (Ctrl+D), выход.")
        sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Непредвиденная ошибка: {e}")
        sys.exit(1)

