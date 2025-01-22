import os
import json
from dotenv import load_dotenv
import fitz  # PyMuPDF
from langchain_openai import ChatOpenAI  # Correct import from langchain-openai
from langchain.schema import HumanMessage, SystemMessage  # For creating structured chat messages

QUESTIONS_PATH = "questions.json"

# Load environment variables
load_dotenv()

def split_text_into_chunks(text: str, chunk_size: int) -> list:
    """
    Splits the text into chunks of a specified maximum size.
    """
    # Trim the text to remove leading/trailing whitespace and reduce multiple spaces to a single space
    cleaned_text = " ".join(text.split())
    words = cleaned_text.split(" ")

    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 > chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def distribute_questions_across_chunks(n_chunks: int, n_questions: int) -> list:
    """
    Distributes a specified number of questions across a specified number of chunks.
    """
    questions_per_chunk = [1] * min(n_chunks, n_questions)
    remaining_questions = n_questions - len(questions_per_chunk)

    if remaining_questions > 0:
        for i in range(len(questions_per_chunk)):
            if remaining_questions == 0:
                break
            questions_per_chunk[i] += 1
            remaining_questions -= 1

    while len(questions_per_chunk) < n_chunks:
        questions_per_chunk.append(0)

    return questions_per_chunk


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
            content="You are an expert interviewer who generates concise technical interview questions. Do not enumerate the questions. Answer only with questions."
        ),
        HumanMessage(
            content=f"Based on the following content, generate {n_questions} technical interview questions:\n{text}"
        ),
    ]

    try:
        print(f"[DEBUG] Sending request to OpenAI with {n_questions} questions.")
        response = chat.invoke(messages)
        questions = response.content.strip().split("\n\n")
        questions = [q.strip() for q in questions if q.strip()]
    except Exception as e:
        print(f"[ERROR] Failed to generate questions: {e}")
        questions = ["An error occurred while generating questions."]

    return questions


def save_questions(questions):
    with open(QUESTIONS_PATH, "w") as f:
        json.dump(questions, f, indent=4)


def generate_and_save_questions_from_pdf(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")
    
    try:
        pdf_text = extract_text_from_pdf(pdf_path)

        if not pdf_text.strip():
            raise RuntimeError("The PDF content is empty or could not be read.")

        chunk_size = 2000
        chunks = split_text_into_chunks(pdf_text, chunk_size)
        n_chunks = len(chunks)

        questions_distribution = distribute_questions_across_chunks(n_chunks, total_questions)
        combined_questions = []

        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_distribution)):
            print(f"[DEBUG] Processing chunk {i + 1} of {n_chunks}")
            if n_questions > 0:
                questions = generate_questions_from_text(chunk, n_questions=n_questions)
                combined_questions.extend(questions)

        if not combined_questions:
            raise RuntimeError("No questions generated from the PDF content.")

        print(f"[INFO] Total questions generated: {len(combined_questions)}")
        save_questions(combined_questions)
        print(f"[INFO] Questions saved to {QUESTIONS_PATH}")

        # Return a status message and the JSON object
        return "Questions generated successfully.", {"questions": combined_questions}
    
    except Exception as e:
        # Handle exceptions and return meaningful error messages
        error_message = f"Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        return error_message, {"questions": []}






import gradio as gr
import json
import os
import time

def generate_and_save_questions_from_pdf3_mock(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")

    if not os.path.exists(pdf_path):
        yield "❌ Error: PDF file not found.", {}
        return

    yield "📄 PDF uploaded successfully. Processing started...", {}

    try:
        # Simulate PDF text extraction and processing
        time.sleep(1)
        pdf_text = "This is some mock PDF text for testing purposes."

        if not pdf_text.strip():
            yield "❌ Error: The PDF content is empty or could not be read.", {}
            return

        chunk_size = 2000
        chunks = [pdf_text[i:i + chunk_size] for i in range(0, len(pdf_text), chunk_size)]
        n_chunks = len(chunks)

        yield f"🔄 Splitting text into {n_chunks} chunks...", {}

        questions_distribution = [total_questions // n_chunks] * n_chunks
        combined_questions = []

        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_distribution)):
            yield f"🔄 Processing chunk {i + 1} of {n_chunks}...", {}
            time.sleep(1)  # Simulating processing time
            combined_questions.append(f"Sample Question from Chunk {i + 1}")

        if not combined_questions:
            yield "❌ Error: No questions generated from the PDF content.", {}
            return

        yield f"✅ Total {len(combined_questions)} questions generated. Saving questions...", {}
        save_path = "generated_questions_from_pdf.json"
        with open(save_path, "w") as f:
            json.dump({"questions": combined_questions}, f)

        yield "✅ PDF processing complete. Questions saved successfully!", {"questions": combined_questions}

    except Exception as e:
        yield f"❌ Error during question generation: {str(e)}", {}

def generate_and_save_questions_from_pdf3_v1(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")

    if not os.path.exists(pdf_path):
        yield "❌ Error: PDF file not found.", {}
        return

    yield "📄 PDF uploaded successfully. Processing started...", {}

    try:
        # Extract text from the PDF file
        pdf_text = extract_text_from_pdf(pdf_path)

        if not pdf_text.strip():
            yield "❌ Error: The PDF content is empty or could not be read.", {}
            return

        # Split the PDF content into chunks
        chunk_size = 2000  # Adjust this as necessary
        chunks = split_text_into_chunks(pdf_text, chunk_size)
        n_chunks = len(chunks)

        yield f"🔄 Splitting text into {n_chunks} chunks...", {}

        # Distribute the total number of questions across chunks
        questions_distribution = distribute_questions_across_chunks(n_chunks, total_questions)
        combined_questions = []

        # Process each chunk and generate questions
        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_distribution)):
            yield f"🔄 Processing chunk {i + 1} of {n_chunks}...", {}
            if n_questions > 0:
                questions = generate_questions_from_text(chunk, n_questions=n_questions)
                combined_questions.extend(questions)

        if not combined_questions:
            yield "❌ Error: No questions generated from the PDF content.", {}
            return

        yield f"✅ Total {len(combined_questions)} questions generated. Saving questions...", {}

        # Save generated questions to a file
        save_path = "generated_questions_from_pdf.json"
        with open(save_path, "w") as f:
            json.dump({"questions": combined_questions}, f)

        yield "✅ PDF processing complete. Questions saved successfully!", {"questions": combined_questions}

    except Exception as e:
        error_message = f"❌ Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        yield error_message, {}

import json
import os

def generate_and_save_questions_from_pdf3(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")

    if not os.path.exists(pdf_path):
        yield "❌ Error: PDF file not found.", {}
        return

    yield "📄 PDF uploaded successfully. Processing started...", {}

    try:
        # Extract text from the PDF file
        pdf_text = extract_text_from_pdf(pdf_path)

        if not pdf_text.strip():
            yield "❌ Error: The PDF content is empty or could not be read.", {}
            return

        # Split the PDF content into chunks
        chunk_size = 2000  # Adjust this as necessary
        chunks = split_text_into_chunks(pdf_text, chunk_size)
        n_chunks = len(chunks)

        yield f"🔄 Splitting text into {n_chunks} chunks...", {}

        # Distribute the total number of questions across chunks
        questions_distribution = distribute_questions_across_chunks(n_chunks, total_questions)
        combined_questions = []

        # Process each chunk and generate questions
        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_distribution)):
            yield f"🔄 Processing chunk {i + 1} of {n_chunks}...", {}
            if n_questions > 0:
                questions = generate_questions_from_text(chunk, n_questions=n_questions)
                combined_questions.extend(questions)

        if not combined_questions:
            yield "❌ Error: No questions generated from the PDF content.", {}
            return

        yield f"✅ Total {len(combined_questions)} questions generated. Saving questions...", {}

        # Save the combined questions in `generated_questions_from_pdf.json` (detailed version)
        detailed_save_path = "generated_questions_from_pdf.json"
        with open(detailed_save_path, "w") as f:
            json.dump({"questions": combined_questions}, f)

        # Save only the questions (overwrite `questions.json` if it already exists)
        simple_save_path = "questions.json"
        with open(simple_save_path, "w") as f:
            json.dump(combined_questions, f)

        yield "✅ PDF processing complete. Questions saved successfully!", {"questions": combined_questions}

    except Exception as e:
        error_message = f"❌ Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        yield error_message, {}



if __name__ == "__main__":
    pdf_path = "professional_machine_learning_engineer_exam_guide_english.pdf"

    try:
        generated_questions = generate_and_save_questions_from_pdf(
            pdf_path, total_questions=5
        )
        print(f"Generated Questions:\n{json.dumps(generated_questions, indent=2)}")
    except Exception as e:
        print(f"Failed to generate questions: {e}")
