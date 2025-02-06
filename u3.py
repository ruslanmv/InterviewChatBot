import gradio as gr
from backend2 import *  # Import everything from the revised backend
import time

def create_manager_app():
    with gr.Blocks(
        title="AI HR Interviewer Manager",
        css="""
        .tab-button {
            background-color: #f0f0f0;
            color: #333;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        .tab-button:hover {
            background-color: #d0d0d0;
        }
        .tab-button.selected {
            background-color: #666;
            color: white;
        }
        .contain { display: flex; flex-direction: column; }
        .gradio-container { height: 100vh !important; overflow-y: auto; } /* Added scroll here */
        #component-0 { height: 100%; }  /* Adjust this selector if needed */
        .chatbot { flex-grow: 1; overflow: auto; height: 650px; } /* Consistent height */
        .chatbot .wrap.svelte-1275q59.wrap.svelte-1275q59 {flex-wrap : nowrap !important}
        .user > div > .message {background-color : #dcf8c6 !important}
        .bot > div > .message {background-color : #f7f7f8 !important}
        """,
    ) as manager_app:
        gr.HTML(
            """
            <div style='text-align: center; margin-bottom: 20px;'>
                <h1 style='font-size: 36px; color: #333;'>AI HR Interviewer Manager</h1>
                <p style='font-size: 18px; color: #666;'>Select your role to start the interview process.</p>
            </div>
        """
        )

        with gr.Row():
            user_role = gr.Dropdown(
                choices=["Admin", "Candidate"],
                label="Select User Role",
                value="Candidate",
            )
            proceed_button = gr.Button("👉 Proceed")

        candidate_ui = gr.Column(visible=False)
        admin_ui = gr.Column(visible=False)

        with candidate_ui:
            gr.Markdown("## 🚀 Candidate Interview")
            # Directly include the candidate app UI without wrapping in another gr.Blocks
            candidate_app = launch_candidate_app_updated()


        with admin_ui:
            gr.Markdown("## 🔒 Admin Panel")
            with gr.Tab("Generate Questions"):
                try:
                    professions_data = load_json_data(PROFESSIONS_FILE)
                    types_data = load_json_data(TYPES_FILE)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Error loading data from JSON files: {e}")
                    professions_data = []  # Initialize as empty lists
                    types_data = []     # on error

                profession_names = [
                    item["profession"] for item in professions_data
                ] if professions_data else [] # Handle empty data
                interview_types = [item["type"] for item in types_data
                ] if types_data else []      # Handle empty data

                with gr.Row():
                    profession_input = gr.Dropdown(
                        label="Select Profession", choices=profession_names
                    )
                    interview_type_input = gr.Dropdown(
                        label="Select Interview Type", choices=interview_types
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
                #num_questions_pdf_input = gr.Number(label="Number of Questions", value=5, precision=0)
                num_questions_pdf_input = gr.Number(
                    label="Number of Questions (1-30)",  # Update label
                    value=5,
                    precision=0,
                    minimum=1,
                    maximum=30,  # Set maximum limit to 30
                )

                pdf_status_output = gr.Textbox(label="Status", lines=3)
                pdf_question_output = gr.JSON(label="Generated Questions")

                generate_pdf_button = gr.Button("Generate Questions from PDF")


                def update_pdf_ui(pdf_path, num_questions):
                    print(f"[DEBUG] PDF Path: {pdf_path}")  # Check if PDF path is passed correctly
                    print(f"[DEBUG] Requested Number of Questions: {num_questions}")  # Debug input

                    all_statuses = []
                    all_questions = []
                    print(f"[DEBUG] Calling generate_and_save_questions_from_pdf3 with {num_questions}")
                    for status, questions in generate_and_save_questions_from_pdf3(pdf_path, num_questions):
                        print(f"[DEBUG] Status: {status}, Questions Generated: {len(questions)}")  # Debug output
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
                    label="Number of Questions (1-30)",  # Limit questions to 30
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


        def show_selected_ui(role):
            if role == "Candidate":
                #Only show the candidate block
                return {candidate_ui: gr.Column(visible=True), admin_ui: gr.Column(visible=False)}

            elif role == "Admin":
                return {candidate_ui: gr.Column(visible=False), admin_ui: gr.Column(visible=True)}
            else:
                return {candidate_ui: gr.Column(visible=False), admin_ui: gr.Column(visible=False)}


        proceed_button.click(
            show_selected_ui,
            inputs=[user_role],
            outputs=[candidate_ui, admin_ui],
        )

    return manager_app

# --- Candidate Interview Implementation (Corrected section below) ---
def launch_candidate_app_updated():
    """Launches the Gradio app for candidates."""
    QUESTIONS_FILE_PATH = "questions.json"

    try:
        questions = read_questions_from_json(QUESTIONS_FILE_PATH)
        if not questions:
            raise ValueError("No questions found.")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"Error loading questions: {e}")
        with gr.Blocks() as error_app:
            gr.Markdown(f"# Error: {e}")
        return error_app

    interview_func, initial_message, _ = conduct_interview_updated(questions)

    def start_interview_ui():
        """Starts the interview."""
        history = []
        initial_combined = (
            initial_message + " Let's begin! Here's the first question: " + questions[0]
        )
        initial_audio_path = convert_text_to_speech_updated(initial_combined)
        history.append(["", initial_combined])  # Correct format: [user, bot]  Empty string for user.
        return history, "", initial_audio_path, gr.Textbox(interactive=True) # Return interactive textbox

    def clear_interview_ui():
        """Clears the interview and resets."""
        # Recreate the object in order to clear the history of the interview
        nonlocal interview_func, initial_message
        interview_func, initial_message, _ = conduct_interview_updated(questions)
        return [], "", None, gr.Textbox(interactive=True) # Return interactive textbox

    def interview_step_wrapper(user_response, audio_response, history):
        """Wrapper for the interview step function."""
        updated_history, user_text, audio_path = interview_func(user_response, audio_response, history)
        # Create a *new* list for history to trigger Gradio update
        new_history = list(updated_history) # Create a copy of the history
        return new_history, "", audio_path, gr.Textbox(value=user_text if user_text is not None else "", interactive= True)

    with gr.Blocks(title="AI HR Interview Assistant") as candidate_app:
        gr.Markdown(
            "<h1 style='text-align: center;'>👋 Welcome to Your AI HR Interview Assistant</h1>"
        )
        start_btn = gr.Button("Start Interview", variant="primary")
        chatbot = gr.Chatbot(label="Interview Chat", height=650)
        audio_input = gr.Audio(
            sources=["microphone"], type="filepath", label="Record Your Answer"
        )
        user_input = gr.Textbox(
            label="Your Response",
            placeholder="Type your answer here or use the microphone...",
            lines=1,
            interactive=True,  # Make the textbox interactive initially
        )
        audio_output = gr.Audio(label="Response Audio", autoplay=True)

        with gr.Row():
            submit_btn = gr.Button("Submit", variant="primary")
            clear_btn = gr.Button("Clear Chat")

        def on_enter_submit(history, user_response):
            """Handles submission when Enter is pressed."""
            if not user_response.strip():
                return history, "", None, gr.Textbox(interactive=True)  # Prevent empty submissions, keep interactive
            updated_history, _, audio_path, new_textbox = interview_step_wrapper(
                user_response, None, history
            )  # No audio on Enter
            return updated_history, "", audio_path, new_textbox # Return the *new* history

        start_btn.click(
            start_interview_ui, inputs=[], outputs=[chatbot, user_input, audio_output, user_input] # Include user_input as output
        )
        audio_input.stop_recording(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output, user_input], # Include user_input as output
        )
        submit_btn.click(
            interview_step_wrapper,
            inputs=[user_input, audio_input, chatbot],
            outputs=[chatbot, user_input, audio_output, user_input],  # Include user_input
        )
        user_input.submit(
            on_enter_submit,
            inputs=[chatbot, user_input],
            outputs=[chatbot, user_input, audio_output, user_input], # Include user_input
        )
        clear_btn.click(
            clear_interview_ui, inputs=[], outputs=[chatbot, user_input, audio_output, user_input] # Include user_input
        )

    return candidate_app
# --- (End of Candidate Interview Implementation) ---


if __name__ == "__main__":
    manager_app = create_manager_app()
    try:
        manager_app.launch(server_name="0.0.0.0", server_port=7860, debug=True, share = True)
    finally:
        cleanup()