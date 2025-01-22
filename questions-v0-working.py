import os
import json
from dotenv import load_dotenv
import fitz  # PyMuPDF
from langchain_openai import ChatOpenAI  # Correct import from langchain-openai
from langchain.schema import HumanMessage, SystemMessage  # For creating structured chat messages
from langchain.text_splitter import RecursiveCharacterTextSplitter

QUESTIONS_PATH = "questions.json"

# Load environment variables
load_dotenv()

# Function to extract text from a PDF using PyMuPDF
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        print(f"[DEBUG] Opening PDF: {pdf_path}")
        with fitz.open(pdf_path) as pdf:
            print(f"[DEBUG] Extracting text from PDF: {pdf_path}")
            for page in pdf:
                text += page.get_text()
    except Exception as e:
        print(f"Error reading PDF: {e}")
        raise RuntimeError("Unable to extract text from PDF.")
    return text

# Function to generate interview questions using ChatOpenAI
def generate_questions_from_text(text, n_questions=5):
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise RuntimeError(
            "OpenAI API key not found. Please add it to your .env file as OPENAI_API_KEY."
        )

    chat = ChatOpenAI(
        openai_api_key=openai_api_key, model="gpt-4", temperature=0.7, max_tokens=750
    )

    messages = [
        SystemMessage(
            content="You are an expert interviewer who generates technical interview questions."
        ),
        HumanMessage(
            content=f"Based on the following content, generate {n_questions} concise technical interview questions:\n{text}"
        ),
    ]

    try:
        print(f"[DEBUG] Sending request to OpenAI with {n_questions} questions.")
        response = chat.invoke(messages)
        questions = response.content.strip().split("\n")
        questions = [q.strip() for q in questions if q.strip()]
    except Exception as e:
        print(f"[ERROR] Failed to generate questions: {e}")
        questions = ["An error occurred while generating questions."]

    return questions

# Function to save questions to a JSON file
def save_questions(questions):
    with open(QUESTIONS_PATH, "w") as f:
        json.dump(questions, f, indent=4)

# Main function to process PDF and generate questions
def generate_and_save_questions_from_pdf(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")

    # Extract text from PDF
    pdf_text = extract_text_from_pdf(pdf_path)

    if not pdf_text.strip():
        raise RuntimeError("The PDF content is empty or could not be read.")

    # Split the text if it's too long
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    chunks = text_splitter.split_text(pdf_text)

    # Calculate questions per chunk
    n_chunks = len(chunks)
    questions_per_chunk = max(1, total_questions // n_chunks)  # Ensure at least 1 question per chunk
    remainder = total_questions % n_chunks

    combined_questions = []
    question_number = 1  # Initialize question counter

    for i, chunk in enumerate(chunks):
        print(f"[DEBUG] Processing chunk {i + 1} of {len(chunks)}")

        # Distribute remaining questions evenly
        n_questions = questions_per_chunk
        if i < remainder:
            n_questions += 1

        questions = generate_questions_from_text(chunk, n_questions=n_questions)

        # Add sequential numbering to questions
        for question in questions:
            combined_questions.append(f"{question_number}. {question}")
            question_number += 1

    print(f"[INFO] Total questions generated: {len(combined_questions)}")

    # Save the questions to a JSON file
    save_questions(combined_questions)
    print(f"[INFO] Questions saved to {QUESTIONS_PATH}")
    return combined_questions

# Example usage
if __name__ == "__main__":
    pdf_path = "professional_machine_learning_engineer_exam_guide_english.pdf"  # Replace with your PDF file path
    try:
        generated_questions = generate_and_save_questions_from_pdf(
            pdf_path, total_questions=10  # You can specify your desired number of questions
        )
        print(f"Generated Questions:\n{json.dumps(generated_questions, indent=2)}")
    except Exception as e:
        print(f"Failed to generate questions: {e}")
