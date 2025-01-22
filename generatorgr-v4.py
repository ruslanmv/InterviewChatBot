import gradio as gr
import json
import time
import os
from generator import generate_questions, load_json_data
from generator import PROFESSIONS_FILE, TYPES_FILE, OUTPUT_FILE

# Load professions and interview types from JSON files
try:
    professions_data = load_json_data(PROFESSIONS_FILE)
    types_data = load_json_data(TYPES_FILE)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading data from JSON files: {e}")
    professions_data = []
    types_data = []

# Extract profession names and interview types for the dropdown menus
profession_names = [item["profession"] for item in professions_data]
interview_types = [item["type"] for item in types_data]

# Define path for the new questions.json file
QUESTIONS_FILE = "questions.json"

def generate_and_save_questions(profession, interview_type, num_questions, progress=gr.Progress()):
    """
    Generates questions using the generate_questions function and saves them to JSON files.
    Provides progress updates.
    """
    profession_info = next(
        (item for item in professions_data if item["profession"] == profession), None
    )
    interview_type_info = next(
        (item for item in types_data if item["type"] == interview_type), None
    )

    if profession_info is None or interview_type_info is None:
        return "Error: Invalid profession or interview type selected.", None

    description = profession_info["description"]
    max_questions = min(int(num_questions), 20)  # Ensure max is 20

    progress(0, desc="Starting question generation...")

    questions = generate_questions(
        profession, interview_type, description, max_questions
    )

    progress(0.5, desc=f"Generated {len(questions)} questions. Saving...")

    # Save the generated questions to the all_questions.json file
    try:
        all_questions = load_json_data(OUTPUT_FILE)
    except (FileNotFoundError, json.JSONDecodeError):
        all_questions = []

    all_questions.append(
        {
            "profession": profession,
            "interview_type": interview_type,
            "description": description,
            "max_questions": max_questions,
            "questions": questions,
        }
    )

    with open(OUTPUT_FILE, "w") as outfile:
        json.dump(all_questions, outfile, indent=4)

    # Save the generated questions to the new questions.json file
    try:
        existing_questions = load_json_data(QUESTIONS_FILE)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_questions = []
    
    existing_questions.extend(questions)

    with open(QUESTIONS_FILE, "w") as outfile:
        json.dump(existing_questions, outfile, indent=4)

    progress(1, desc="Questions saved.")

    return (
        f"✅ Questions generated and saved for {profession} ({interview_type}). Max questions: {max_questions}",
        questions,
    )


def update_max_questions(interview_type):
    """
    Updates the default value of the number input based on the selected interview type.
    """
    interview_type_info = next(
        (item for item in types_data if item["type"] == interview_type), None
    )
    if interview_type_info:
        default_max_questions = interview_type_info.get("max_questions", 5)
        return gr.update(value=default_max_questions, minimum=1, maximum=20)
    else:
        return gr.update(value=5, minimum=1, maximum=20)


with gr.Blocks() as demo:
    gr.Markdown("## 📄 Interview Question Generator for IBM CIC")
    with gr.Row():
        profession_input = gr.Dropdown(label="Select Profession", choices=profession_names)
        interview_type_input = gr.Dropdown(label="Select Interview Type", choices=interview_types)

    num_questions_input = gr.Number(
        label="Number of Questions (1-20)", value=5, precision=0, minimum=1, maximum=20
    )

    generate_button = gr.Button("Generate Questions")

    output_text = gr.Textbox(label="Output")
    question_output = gr.JSON(label="Generated Questions")

    # Update num_questions_input when interview_type_input changes
    interview_type_input.change(
        fn=update_max_questions,
        inputs=interview_type_input,
        outputs=num_questions_input,
    )

    generate_button.click(
        generate_and_save_questions,
        inputs=[profession_input, interview_type_input, num_questions_input],
        outputs=[output_text, question_output],
    )

if __name__ == "__main__":
    demo.queue().launch()