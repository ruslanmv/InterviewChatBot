import gradio as gr
import json
from generator import generate_questions, load_json_data  # Assuming generator.py is your updated script
from generator import PROFESSIONS_FILE, TYPES_FILE, OUTPUT_FILE

# Load professions and interview types from JSON files
try:
    professions_data = load_json_data(PROFESSIONS_FILE)
    types_data = load_json_data(TYPES_FILE)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading data from JSON files: {e}")
    professions_data = []  # Provide default values to avoid further errors
    types_data = []

# Extract profession names and interview types for the dropdown menus
profession_names = [item["profession"] for item in professions_data]
interview_types = [item["type"] for item in types_data]

def generate_and_save_questions(profession, interview_type):
    """
    Generates questions using the generate_questions function and saves them to a JSON file.
    """
    profession_info = next((item for item in professions_data if item["profession"] == profession), None)
    interview_type_info = next((item for item in types_data if item["type"] == interview_type), None)
    
    if profession_info is None or interview_type_info is None:
        return "Error: Invalid profession or interview type selected.", None

    description = profession_info["description"]
    max_questions = interview_type_info.get("max_questions", 5)

    questions = generate_questions(profession, interview_type, description, max_questions)

    # Save the generated questions to the all_questions.json file
    try:
        all_questions = load_json_data(OUTPUT_FILE)
    except (FileNotFoundError, json.JSONDecodeError):
        all_questions = []

    all_questions.append({
        "profession": profession,
        "interview_type": interview_type,
        "description": description,
        "max_questions": max_questions,
        "questions": questions
    })

    with open(OUTPUT_FILE, "w") as outfile:
        json.dump(all_questions, outfile, indent=4)

    return f"✅ Questions generated and saved for {profession} ({interview_type}).", questions

with gr.Blocks() as demo:
    gr.Markdown("## 📄 Interview Question Generator for IBM CIC")
    with gr.Row():
        profession_input = gr.Dropdown(label="Select Profession", choices=profession_names)
        interview_type_input = gr.Dropdown(label="Select Interview Type", choices=interview_types)
        generate_button = gr.Button("Generate Questions")
    
    output_text = gr.Textbox(label="Output")
    question_output = gr.JSON(label="Generated Questions")

    generate_button.click(
        generate_and_save_questions,
        inputs=[profession_input, interview_type_input],
        outputs=[output_text, question_output]
    )

if __name__ == "__main__":
    demo.launch()