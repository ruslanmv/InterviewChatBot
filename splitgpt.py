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
        print(f"[DEBUG] Raw questions from LLM: {questions}")

        formatted_questions = []
        for i, q in enumerate(questions):
            formatted_questions.append(f"Question {i+1}: {q}")

        print(f"[DEBUG] Formatted questions: {formatted_questions}")
        return formatted_questions
    except Exception as e:
        print(f"[ERROR] Failed to generate questions: {e}")
        return ["An error occurred while generating questions."]




def save_questions(questions):
    with open(QUESTIONS_PATH, "w") as f:
        json.dump(questions, f, indent=4)



import os
import json
import re


def generate_and_save_questions_from_pdf3(pdf_path, total_questions=5):
    print(f"[INFO] Generating questions from PDF: {pdf_path}")
    print(f"[DEBUG] Number of total questions to generate: {total_questions}")

    if not os.path.exists(pdf_path):
        yield "❌ Error: PDF file not found.", []
        return

    yield "📄 PDF uploaded successfully. Processing started...", []

    try:
        # 1. Extract text from the PDF
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text.strip():
            yield "❌ Error: The PDF content is empty or could not be read.", []
            return

        # 2. Split the PDF content into chunks
        chunk_size = 2000  # Adjust as necessary
        chunks = split_text_into_chunks(pdf_text, chunk_size)
        n_chunks = len(chunks)

        yield f"🔄 Splitting text into {n_chunks} chunks...", []

        # 3. Distribute total_questions evenly across the chunks
        base = total_questions // n_chunks
        remainder = total_questions % n_chunks
        questions_per_chunk = [base] * n_chunks
        for i in range(remainder):
            questions_per_chunk[i] += 1

        print(f"[DEBUG] Questions per chunk distribution: {questions_per_chunk}")

        combined_questions = []

        # Helper function to split any chunk's output into individual questions
        def split_into_individual_questions(text_block):
            """
            Attempts to split a text block that might contain multiple questions
            (like '1. Some question? 2. Another question?') into separate items.
            """
            # 1) Remove any "Question X:" prefix (e.g., "Question 1: ")
            text_block = re.sub(r'Question\s*\d+\s*:\s*', '', text_block, flags=re.IGNORECASE)

            # 2) Split on patterns like "1. Something", "2. Something"
            #    This looks for one or more digits, then a dot, then whitespace: "(\d+\.\s+)"
            splitted = re.split(r'\d+\.\s+', text_block.strip())

            # 3) Clean up and filter out empty items
            splitted = [s.strip() for s in splitted if s.strip()]

            return splitted

        # 4. Process each chunk and generate questions
        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_per_chunk)):
            yield f"🔄 Processing chunk {i+1} of {n_chunks} with {n_questions} questions...", []
            
            if n_questions > 0:
                # This function returns either a list of questions or a single string with multiple questions
                questions_output = generate_questions_from_text(chunk, n_questions=n_questions)

                if isinstance(questions_output, list):
                    # If it's already a list, we further ensure each item is split if needed
                    for item in questions_output:
                        combined_questions.extend(split_into_individual_questions(str(item)))
                else:
                    # If it's a single string, we split it
                    combined_questions.extend(split_into_individual_questions(str(questions_output)))

        # 5. Check if the number of generated questions matches the desired total
        if len(combined_questions) != total_questions:
            yield f"⚠️ Warning: Expected {total_questions}, but generated {len(combined_questions)}.", []

        yield f"✅ Total {len(combined_questions)} questions generated. Saving questions...", []

        # 6. Save the combined questions in `generated_questions_from_pdf.json`
        detailed_save_path = "generated_questions_from_pdf.json"
        with open(detailed_save_path, "w", encoding="utf-8") as f:
            json.dump({"questions": combined_questions}, f, indent=4, ensure_ascii=False)

        # 7. Save only the questions (overwrite `questions.json` if it already exists)
        simple_save_path = "questions.json"
        with open(simple_save_path, "w", encoding="utf-8") as f:
            json.dump(combined_questions, f, indent=4, ensure_ascii=False)

        yield "✅ PDF processing complete. Questions saved successfully!", combined_questions

    except Exception as e:
        error_message = f"❌ Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        yield error_message, []

def generate_questions_from_job_description_old(job_description, num_questions):
    print(f"[DEBUG] Generating {num_questions} questions from job description.")

    if not job_description.strip():
        return "❌ Error: Job description is empty.", []

    try:
        questions = generate_questions_from_text(job_description, num_questions=num_questions)

        if not questions:
            return "❌ Error: No questions generated.", []

        return "✅ Questions generated successfully!", questions

    except Exception as e:
        error_message = f"❌ Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        return error_message, []

import os
import json
import math
import re
import os
import json
import math
import re

def distribute_questions_evenly(total_questions, n_chunks):
    base = total_questions // n_chunks
    remainder = total_questions % n_chunks

    questions_per_chunk = [base] * n_chunks

    # Distribute the remainder by incrementing the first `remainder` chunks
    for i in range(remainder):
        questions_per_chunk[i] += 1

    return questions_per_chunk


def generate_questions_from_job_description(job_description, total_questions=5):
    print(f"[DEBUG] Generating {total_questions} questions from job description.")

    if not job_description.strip():
        return "❌ Error: Job description is empty.", []

    try:
        # 1. Split the job description into chunks
        chunk_size = 2000  # Adjust as necessary
        chunks = split_text_into_chunks(job_description, chunk_size)
        n_chunks = len(chunks)

        print(f"[DEBUG] Splitting text into {n_chunks} chunks...")

        # 2. Distribute total_questions evenly across the chunks
        questions_per_chunk = distribute_questions_evenly(total_questions, n_chunks)
        print(f"[DEBUG] Questions per chunk distribution: {questions_per_chunk}")

        combined_questions = []

        # Helper function to split any chunk's output into individual questions
        def split_into_individual_questions(text_block):
            """
            Attempts to split a text block that might contain multiple questions
            (like '1. Some question? 2. Another question?') into separate items.
            """
            # Remove any "Question X:" prefix (e.g., "Question 1: ")
            text_block = re.sub(r'Question\s*\d+\s*:\s*', '', text_block, flags=re.IGNORECASE)

            # Split on patterns like "1. Something", "2. Something"
            splitted = re.split(r'\d+\.\s+', text_block.strip())

            # Clean up and filter out empty items
            return [s.strip() for s in splitted if s.strip()]

        # 3. Process each chunk and generate questions
        for i, (chunk, n_questions) in enumerate(zip(chunks, questions_per_chunk)):
            print(f"[DEBUG] Processing chunk {i+1} of {n_chunks} with {n_questions} questions...")
            
            if n_questions > 0:
                questions_output = generate_questions_from_text(chunk, n_questions=n_questions)

                if isinstance(questions_output, list):
                    for item in questions_output:
                        combined_questions.extend(split_into_individual_questions(str(item)))
                else:
                    combined_questions.extend(split_into_individual_questions(str(questions_output)))

        if len(combined_questions) != total_questions:
            print(f"⚠️ Warning: Expected {total_questions}, but generated {len(combined_questions)}.")

        print(f"✅ Total {len(combined_questions)} questions generated. Saving questions...")

        # Save the combined questions in `generated_questions_from_job_description.json`
        detailed_save_path = "generated_questions_from_job_description.json"
        with open(detailed_save_path, "w", encoding="utf-8") as f:
            json.dump({"questions": combined_questions}, f, indent=4, ensure_ascii=False)

        # Save only the questions (overwrite `questions.json` if it already exists)
        simple_save_path = "questions.json"
        with open(simple_save_path, "w", encoding="utf-8") as f:
            json.dump(combined_questions, f, indent=4, ensure_ascii=False)

        return "✅ Job description processing complete. Questions saved successfully!", combined_questions

    except Exception as e:
        error_message = f"❌ Error during question generation: {str(e)}"
        print(f"[ERROR] {error_message}")
        return error_message, []


if __name__ == "__main__":
    pdf_path = "professional_machine_learning_engineer_exam_guide_english.pdf"  # Replace with your PDF path

    try:
        # Using the generator to get the results
        for status, questions in generate_and_save_questions_from_pdf3(pdf_path, total_questions=5):
            print(status)  # Print the status message
            if questions:
                print(json.dumps(questions, indent=2))  # Print the questions if available
    except Exception as e:
        print(f"Failed to generate questions: {e}")