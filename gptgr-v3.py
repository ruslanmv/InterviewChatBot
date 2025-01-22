import os
import json
from collections import deque
from dotenv import load_dotenv
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

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

# Conduct interview and handle user input
def conduct_interview(questions, language="English", history_limit=5):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY.")

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    conversation_history = deque(maxlen=history_limit)
    system_prompt = (f"You are Sarah, an empathetic HR interviewer conducting a technical interview in {language}. "
                     "Respond to user follow-up questions politely and concisely. If the user is confused, provide clear clarification.")

    interview_data = []
    current_question_index = [0]  # Use a list to hold the index

    initial_message = ("👋 Hi there, I'm Sarah, your friendly AI HR assistant! "
                       "I'll guide you through a series of interview questions to learn more about you. "
                       "Take your time and answer each question thoughtfully.")

    def interview_step(user_input, history):
        if user_input.lower() in ["exit", "quit"]:
            history.append((None, "The interview has ended at your request. Thank you for your time!"))
            return history, ""

        question_text = questions[current_question_index[0]]
        history_content = "\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in conversation_history])
        combined_prompt = (f"{system_prompt}\n\nPrevious conversation history:\n{history_content}\n\n"
                           f"Current question: {question_text}\nUser's input: {user_input}\n\n"
                           "Respond in a warm and conversational way, offering natural follow-ups if needed.")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_prompt)
        ]

        response = chat.invoke(messages)
        response_content = response.content.strip()

        conversation_history.append({"question": question_text, "answer": user_input})
        interview_data.append({"question": question_text, "answer": user_input})
        history.append((user_input, None))
        history.append((None, response_content))

        if current_question_index[0] + 1 < len(questions):
            current_question_index[0] += 1
            next_question = f"Alright, here's the next one: {questions[current_question_index[0]]}"
            history.append((None, next_question))
            return history, ""
        else:
            history.append((None, "That wraps up our interview. Thank you so much for your responses—it's been great learning more about you!"))
            return history, ""

    return interview_step, initial_message

# Gradio interface
def main():
    QUESTIONS_FILE_PATH = "questions.json"  # Ensure you have a questions.json file with your interview questions

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        interview_func, initial_message = conduct_interview(questions)

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

            chatbot = gr.Chatbot(label="Interview Chat", elem_id="chatbot", height=650)
            user_input = gr.Textbox(label="Your Response", placeholder="Type your answer here...", lines=1)

            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                clear_btn = gr.Button("Clear Chat")

            def start_interview():
                history = []
                history.append((None, initial_message))
                history.append((None, "Let's begin! Here's your first question: " + questions[0]))
                return history, ""

            def clear_interview():
                return [], ""

            def interview_step(user_response, history):
                return interview_func(user_response, history)

            def on_enter_submit(history, user_response):
                if not user_response.strip():
                    return history, ""
                return interview_step(user_response, history)

            start_btn.click(start_interview, inputs=[], outputs=[chatbot, user_input])
            submit_btn.click(interview_step, inputs=[user_input, chatbot], outputs=[chatbot, user_input])
            user_input.submit(on_enter_submit, inputs=[chatbot, user_input], outputs=[chatbot, user_input])
            clear_btn.click(clear_interview, inputs=[], outputs=[chatbot, user_input])

        demo.launch()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
