import gradio as gr
from questions import generate_and_save_questions_from_pdf

def generate_questions(pdf_file, num_questions):
  """
  Generates questions from a PDF file using the questions.py script.

  Args:
    pdf_file: The PDF file to generate questions from.
    num_questions: The number of questions to generate.

  Returns:
    A string indicating success or failure, and a list of generated questions.
  """
  try:
    questions = generate_and_save_questions_from_pdf(pdf_file.name, total_questions=int(num_questions))
    return f"✅ {len(questions)} questions generated and saved.", questions
  except Exception as e:
    return f"❌ Error: {e}", None


with gr.Blocks() as demo:
  gr.Markdown("## 📄 PDF Question Generator")
  with gr.Row():
    pdf_input = gr.File(label="Upload PDF File", type="filepath")  # Changed type to "filepath"
    num_questions_input = gr.Number(label="Number of Questions", value=5)
  generate_button = gr.Button("Generate Questions")
  output_text = gr.Textbox(label="Output")
  question_output = gr.JSON(label="Generated Questions")

  generate_button.click(
      generate_questions,
      inputs=[pdf_input, num_questions_input],
      outputs=[output_text, question_output]
  )

if __name__ == "__main__":
  demo.launch()