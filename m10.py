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
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file or enter in the API Key Panel.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4o", temperature=0.7, max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)
    system_prompt = (f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
                     "Respond to user follow-up questions politely and concisely. "
                     "Engage in a natural conversation flow. After asking a question from the provided list, wait for the user's answer. "
                     "If the user provides a short answer, or if it's natural in a conversation, ask a follow-up question to dig deeper or clarify their response before moving to the next question from the list. "
                     "Only move to the next question from the list after you have sufficiently explored the current question and the user's answer. "
                     "If the user is confused, provide clear clarification.")

    interview_data = []
    current_question_index = [0]  # Use a list to hold the index
    is_interview_finished = [False] # Use a list to hold boolean, for mutable access in inner function
    waiting_for_answer = [False] # Track if LLM is waiting for answer after a follow-up question

    initial_message = ("👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
                       "I'll guide you through a series of interview questions to learn more about you. "
                       "Take your time and answer each question thoughtfully. Let's begin! Here's your first question: ")
    final_message = "That wraps up our interview. Thank you so much for your responses—it's been great learning more about you!"
    print(f"DEBUG - conduct_interview setup time: {time.time() - start_time:.2f} seconds")

    def interview_step(user_input, audio_input, history):
        nonlocal current_question_index, is_interview_finished, waiting_for_answer

        step_start_time = time.time()

        # Transcribe audio input if provided
        if audio_input:
            user_input = transcribe_audio(audio_input)
            print("Transcription:", user_input)

        if user_input.lower() in ["exit", "quit"]:
            history.append({"role": "assistant", "content": "The interview has ended at your request. Thank you for your time!"})
            is_interview_finished[0] = True
            return history, "", None

        # If interview is finished, do nothing
        if is_interview_finished[0]:
            return history, "", None

        if waiting_for_answer[0]: # If waiting for answer to a follow-up, process answer and then ask next main question
            waiting_for_answer[0] = False # Reset flag
            question_text = questions[current_question_index[0]] # Still the same main question
        else:
            question_text = questions[current_question_index[0]]


        history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
        combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                            f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                            "Respond in a warm and conversational way, offering natural follow-ups if needed. If you ask a follow-up question, remember to wait for the user's response before proceeding to the next main interview question.")

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

        # Check if the response is a question to determine if we should wait for another user input before moving to next main question.
        if "?" in response_content: # Simple check if response ends with a question mark. Can be improved with more sophisticated NLP.
            waiting_for_answer[0] = True
            print("DEBUG - Waiting for answer to follow-up question.")
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", audio_file_path
        elif current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Alright, let's move on. {questions[current_question_index[0]]}"
            next_question_audio_path = convert_text_to_speech(next_question)
            history.append({"role": "assistant", "content": next_question})
            print("DEBUG - Moving to next main question.")
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", next_question_audio_path

        else:
            # Convert final message to speech and play it
            final_message_audio_path = convert_text_to_speech(final_message)
            history.append({"role": "assistant", "content": final_message})

            # Convert the last question to speech (optional, if you want to replay the last question)
            # last_question_audio_path = convert_text_to_speech(questions[current_question_index[0]])
            is_interview_finished[0] = True
            print("DEBUG - Interview finished.")
            print(f"DEBUG - Interview step time: {time.time() - step_start_time:.2f} seconds")
            return history, "", final_message_audio_path

    return interview_step, initial_message, final_message

# Gradio interface
def main():
    QUESTIONS_FILE_PATH = "questions.json"  # Ensure you have a questions.json file with your interview questions

    # Check if API key is loaded initially
    initial_api_key_loaded = bool(os.getenv("OPENAI_API_KEY"))
    initial_api_key_status_message = "✅ API Key loaded from .env file." if initial_api_key_loaded else "❌ API Key not loaded. Please enter below."

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message, final_message = conduct_interview(questions)

        css = """
        .contain { display: flex; flex-direction: column; }
        .gradio-container { height: 100vh !important; overflow-y: auto; } /* Added scroll here */
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
                # Combine initial message and first question
                first_question = questions[0]
                combined_message = initial_message + first_question

                # Convert combined message to speech
                combined_audio_path = convert_text_to_speech(combined_message)

                history.append({"role": "assistant", "content": combined_message})

                print(f"DEBUG - Initial message audio time: {time.time() - start_time:.2f} seconds")

                return history, "", combined_audio_path

            def clear_interview():
                # Reset the interview state
                interview_func, initial_message, final_message = conduct_interview(questions)
                return [], "", None

            def interview_step_wrapper(user_response, audio_response, history):
                history, _, audio_path = interview_func(user_response, audio_response, history)
                time.sleep(0.1)  # Reduced delay
                return history, "", audio_path

            def on_enter_submit(history, user_response):
                if not user_response.strip():
                    return history, "", None
                history, _, audio_path = interview_func(user_response, None, history)
                time.sleep(0.1)  # Reduced delay
                return history, "", audio_path

            audio_input.stop_recording(interview_step_wrapper, inputs=[user_input, audio_input, chatbot], outputs=[chatbot, user_input, audio_output])
            start_btn.click(start_interview, inputs=[], outputs=[chatbot, user_input, audio_output])
            submit_btn.click(interview_step_wrapper, inputs=[user_input, audio_input, chatbot], outputs=[chatbot, user_input, audio_output])
            user_input.submit(on_enter_submit, inputs=[chatbot, user_input], outputs=[chatbot, user_input, audio_output])
            clear_btn.click(clear_interview, inputs=[], outputs=[chatbot, user_input, audio_output])

            with gr.Tab("Admin Panel", id="admin_tab"):
                with gr.Tab("API Key Settings"):
                    gr.Markdown("### OpenAI API Key Configuration")
                    api_key_input = gr.Textbox(label="Enter your OpenAI API Key", type="password", placeholder="••••••••••••••••••••••••••••••••")
                    api_key_status_output = gr.Textbox(label="API Key Status", value=initial_api_key_status_message, interactive=False)
                    update_api_key_button = gr.Button("Update API Key")
                    gr.Markdown("*This application does not store your API key. It is used only for this session and is not persisted when you close the app.*")

                    def update_api_key(api_key):
                        os.environ["OPENAI_API_KEY"] = api_key  # Caution: Modifying os.environ is session-based
                        global interview_func, initial_message, final_message  # Declare globals to update them
                        try:
                            interview_func, initial_message, final_message = conduct_interview(questions)  # Re-init interview function
                            return "✅ API Key Updated and Loaded."
                        except RuntimeError as e:
                            return f"❌ API Key Update Failed: {e}"

                    update_api_key_button.click(
                        update_api_key,
                        inputs=[api_key_input],
                        outputs=[api_key_status_output],
                    )

                # with gr.Tab("Generate Questions"):
                with gr.Tab("Generate Questions"):
                    try:
                        # Assuming these are defined in backend2.py
                        from backend2 import (
                            load_json_data,
                            PROFESSIONS_FILE,
                            TYPES_FILE,
                            generate_questions_manager,
                            update_max_questions,
                            generate_and_save_questions_from_pdf3,
                            generate_questions_from_job_description,
                            cleanup
                        )

                        professions_data = load_json_data(PROFESSIONS_FILE)
                        types_data      = load_json_data(TYPES_FILE)

                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        print(f"Error loading data from JSON files: {e}")
                        professions_data = []
                        types_data      = []

                    profession_names = [
                        item["profession"] for item in professions_data
                    ] if professions_data else []

                    interview_types = [
                        item["type"] for item in types_data
                    ] if types_data else []

                    with gr.Row():
                        profession_input = gr.Dropdown(
                            label="Select Profession",
                            choices=profession_names
                        )
                        interview_type_input = gr.Dropdown(
                            label="Select Interview Type",
                            choices=interview_types
                        )

                        num_questions_input = gr.Number(
                            label="Number of Questions (1-20)",
                            value=5,
                            precision=0,
                            minimum=1,
                            maximum=20,
                        )
                        overwrite_input = gr.Checkbox(
                            label="Overwrite all_questions.json?", value=True
                        )

                        # Update num_questions_input when interview_type_input changes
                        interview_type_input.change(
                            fn=update_max_questions,
                            inputs=interview_type_input,
                            outputs=num_questions_input,
                        )

                        generate_button = gr.Button("Generate Questions")

                        output_text = gr.Textbox(label="Output")
                        question_output = gr.JSON(label="Generated Questions")

                        generate_button.click(
                            generate_questions_manager,
                            inputs=[
                                profession_input,
                                interview_type_input,
                                num_questions_input,
                                overwrite_input,
                            ],
                            outputs=[output_text, question_output],
                        )

                    with gr.Tab("Generate from PDF"):
                        gr.Markdown("### 📄 Upload PDF for Question Generation")
                        pdf_file_input = gr.File(label="Upload PDF File", type="filepath")
                        num_questions_pdf_input = gr.Number(
                            label="Number of Questions (1-30)",
                            value=5,
                            precision=0,
                            minimum=1,
                            maximum=30,
                        )

                        pdf_status_output = gr.Textbox(label="Status", lines=3)
                        pdf_question_output = gr.JSON(label="Generated Questions")

                        generate_pdf_button = gr.Button("Generate Questions from PDF")

                        def update_pdf_ui(pdf_path, num_questions):
                            print(f"[DEBUG] PDF Path: {pdf_path}")
                            print(f"[DEBUG] Requested Number of Questions: {num_questions}")

                            all_statuses = []
                            all_questions = []
                            print(f"[DEBUG] Calling generate_and_save_questions_from_pdf3 with {num_questions}")
                            for status, questions in generate_and_save_questions_from_pdf3(pdf_path, num_questions):
                                print(f"[DEBUG] Status: {status}, Questions Generated: {len(questions)}")
                                all_statuses.append(status)
                                all_questions.append(questions)

                            combined_status = "\n".join(all_statuses)
                            final_questions = all_questions[-1] if all_questions else []

                            return gr.update(value=combined_status), gr.update(value=final_questions)

                        generate_pdf_button.click(
                            update_pdf_ui,
                            inputs=[pdf_file_input, num_questions_pdf_input],
                            outputs=[pdf_status_output, pdf_question_output],
                        )

                    with gr.Tab("Generate from Job Description"):
                        gr.Markdown("### 📝 Enter Job Description for Question Generation")

                        job_description_input = gr.Textbox(label="Job Description", placeholder="Type or paste the job description here...", lines=6)
                        num_questions_job_input = gr.Number(
                            label="Number of Questions (1-30)",
                            value=5,
                            precision=0,
                            minimum=1,
                            maximum=30
                        )

                        job_status_output = gr.Textbox(label="Status", lines=3)
                        job_question_output = gr.JSON(label="Generated Questions")

                        generate_job_button = gr.Button("Generate Questions from Job Description")

                        def update_job_description_ui(job_description, num_questions):
                            print(f"[DEBUG] Job Description Length: {len(job_description)} characters")
                            print(f"[DEBUG] Requested Number of Questions: {num_questions}")

                            status, questions = generate_questions_from_job_description(job_description, num_questions)
                            return gr.update(value=status), gr.update(value=questions)

                        generate_job_button.click(
                            update_job_description_ui,
                            inputs=[job_description_input, num_questions_job_input],
                            outputs=[job_status_output, job_question_output],
                        )

            demo.launch()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()