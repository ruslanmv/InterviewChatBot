import os
import json
from collections import deque
from dotenv import load_dotenv
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from openai import OpenAI
import tempfile
import time

# Load environment variables
load_dotenv()

# Function to read questions from JSON
def read_questions_from_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    with open(file_path, 'r') as f:
        questions_list = json.load(f)

    if not questions_list:
        raise ValueError("The JSON file is empty or has invalid content.")

    return questions_list

# Function to convert text to speech
def convert_text_to_speech(text):
    start_time = time.time()
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)

        # Save the audio stream to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            for chunk in response.iter_bytes():
                tmp_file.write(chunk)
            temp_audio_path = tmp_file.name

        print(f"DEBUG - Text-to-speech conversion time: {time.time() - start_time:.2f} seconds")
        return temp_audio_path

    except Exception as e:
        print(f"Error during text-to-speech conversion: {e}")
        return None

# Function to transcribe audio
def transcribe_audio(audio_file_path):
    start_time = time.time()
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        print(f"DEBUG - Audio transcription time: {time.time() - start_time:.2f} seconds")
        return transcription.text
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return None

# Conduct interview and handle user input
def conduct_interview(questions, language="English", history_limit=5):
    start_time = time.time()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4o", temperature=0.7, max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)
    system_prompt = (f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
                     "Respond to user follow-up questions politely and concisely. If the user is confused, provide clear clarification.")

    interview_data = []
    current_question_index = [0]  # Use a list to hold the index

    initial_message = ("👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
                       "I'll guide you through a series of interview questions to learn more about you. "
                       "Take your time and answer each question thoughtfully.")
    final_message = "That wraps up our interview. Thank you so much for your responses—it's been great learning more about you!"
    print(f"DEBUG - conduct_interview setup time: {time.time() - start_time:.2f} seconds")

    def interview_step(user_input, audio_input, history):
        step_start_time = time.time()

        # Transcribe audio input if provided
        if audio_input:
            user_input = transcribe_audio(audio_input)
            print("Transcription:", user_input)

        if user_input.lower() in ["exit", "quit"]:
            history.append({"role": "assistant", "content": "The interview has ended at your request. Thank you for your time!"})
            return history, "", None

        question_text = questions[current_question_index[0]]
        history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
        combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                           f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                           "Respond in a warm and conversational way, offering natural follow-ups if needed.")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt)
        ]

        chat_start_time = time.time()
        response = chat.invoke(messages)
        print(f"DEBUG - Chat response time: {time.time() - chat_start_time:.2f} seconds")
        response_content = response.content.strip()

        # Convert response to speech
        audio_file_path = convert_text_to_speech(response_content)

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})

        # Use the correct format for messages
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response_content})

        if current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Alright, let's move on. {questions[current_question_index[0]]}"
            next_question_audio_path = convert_text_to_speech(next_question)
            history.append({"role": "assistant", "content": next_question})
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", next_question_audio_path
        else:
            # Convert final message to speech and play it
            final_message_audio_path = convert_text_to_speech(final_message)
            history.append({"role": "assistant", "content": final_message})
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", final_message_audio_path

    return interview_step, initial_message, final_message

# Gradio interface
def main():
    QUESTIONS_FILE_PATH = "questions.json"  # Ensure you have a questions.json file with your interview questions

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message, final_message = conduct_interview(questions)

        css = """
        .contain { display: flex; flex-direction: column; }
        .gradio-container { height: 100vh !important; }
        #component-0 { height: 100%; }
        .chatbot { flex-grow: 1; overflow: auto; height: 100px; }
        .chatbot .wrap.svelte-1275q59.wrap.svelte-1275q59 {flex-wrap : nowrap !important}
        .user > div > .message {background-color : #dcf8c6 !important}
        .bot > div > .message {background-color : #f7f7f8 !important}
        """

        with gr.Blocks(css=css) as demo:
            gr.Markdown("""
            <h1 style='text-align: center; margin-bottom: 1rem'>👋 Welcome to Your AI HR Interview Assistant</h1>
            """)

            start_btn = gr.Button("Start Interview", variant="primary")

            gr.Markdown("""
            <p style='text-align: center; margin-bottom: 1rem'>I will ask you a series of questions. Please answer honestly and thoughtfully. When you are ready, click "Start Interview" to begin.</p>
            """)

            chatbot = gr.Chatbot(label="Interview Chat", elem_id="chatbot", height=650, type='messages')
            audio_input = gr.Audio(sources=["microphone"], type="filepath", label="Record Your Answer")
            user_input = gr.Textbox(label="Your Response", placeholder="Type your answer here or use the microphone...", lines=1)

            audio_output = gr.Audio(label="Response Audio", autoplay=True)

            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                clear_btn = gr.Button("Clear Chat")

            def start_interview():
                history = []

                # Convert and play initial message
                start_time = time.time()
                initial_audio_path = convert_text_to_speech(initial_message)

                # Combine initial message and first question
                first_question = "Let's begin! Here's your first question: " + questions[0]
                combined_message = initial_message + " " + first_question

                # Convert combined message to speech
                combined_audio_path = convert_text_to_speech(combined_message)

                history.append({"role": "assistant", "content": combined_message})

                print(f"DEBUG - Initial message audio time: {time.time() - start_time:.2f} seconds")

                return history, "", combined_audio_path

            def clear_interview():
                return [], "", None

            def interview_step_wrapper(user_response, audio_response, history):
                history, _, audio_path = interview_func(user_response, audio_response, history)
                time.sleep(0.1)  # Reduced delay
                return history, "", audio_path

            def on_enter_submit(history, user_response):
                if not user_response.strip():
                    return history, "", None
                history, _, audio_path = interview_step_wrapper(user_response, None, history)
                time.sleep(0.1)  # Reduced delay
                return history, "", audio_path

            audio_input.stop_recording(interview_step_wrapper, inputs=[user_input, audio_input, chatbot], outputs=[chatbot, user_input, audio_output])
            start_btn.click(start_interview, inputs=[], outputs=[chatbot, user_input, audio_output])
            submit_btn.click(interview_step_wrapper, inputs=[user_input, audio_input, chatbot], outputs=[chatbot, user_input, audio_output])
            user_input.submit(on_enter_submit, inputs=[chatbot, user_input], outputs=[chatbot, user_input, audio_output])
            clear_btn.click(clear_interview, inputs=[], outputs=[chatbot, user_input, audio_output])

        demo.launch()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()