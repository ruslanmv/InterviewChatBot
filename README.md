# HR Interviewer AI

This project implements an AI-powered HR interviewer that conducts interviews and generates reports based on a provided knowledge base. The interviewer uses Retrieval-Augmented Generation (RAG) to create contextually relevant questions based on an uploaded document (e.g., job description, company policies).

Interview-HR-Bot: This chatbot offers a realistic interview simulation with customizable questions based on your industry. It provides feedback on your answers and tracks your progress.


## Features

*   **RAG-Based Interviewing:** Asks questions tailored to the specific role and company based on the uploaded document.
*   **Audio Interaction:**  Supports voice input and output using speech-to-text and text-to-speech.
*   **Report Generation:** Creates a comprehensive HR report summarizing the interview, including candidate assessment, strengths, weaknesses, and recommendations.
*   **Admin Settings:** Allows administrators to configure settings like audio and the AI interviewer's voice.
*   **Document Upload:** Supports uploading documents in TXT, PDF, or DOCX formats to serve as the knowledge base for the interview.




Project Structure:
```bash
hr_interviewer/
├── app.py          # Main Gradio application
├── ai_config.py   # AI model configuration and utilities
├── knowledge_retrieval.py  # RAG-based question generation and report creation
├── prompt_instructions.py # Prompts for the AI
├── settings.py      # Interview settings (e.g., language, number of questions)
├── utils.py        # Utility functions (e.g., saving interview history)
├── requirements.txt # Project dependencies
├── knowledge/     # Directory to store uploaded documents and FAISS index
│   └── ...        # (Uploaded documents and index files)
└── questionnaire.csv # CSV file with predefined interview questions (optional)
```
## Prerequisites

*   **Anaconda:** You'll need Anaconda or Miniconda installed to create the virtual environment. Download and install from [https://www.anaconda.com/download/](https://www.anaconda.com/download/).
*   **OpenAI API Key:** You need an OpenAI API key to use the OpenAI models for text generation, embeddings, and speech-to-text/text-to-speech. Sign up or log in at [https://platform.openai.com/](https://platform.openai.com/) to get your key.

## Setup

1.  **Clone the Repository:**

    ```bash
    git clone   
    cd hr_interviewer_ai
    ```

2.  **Create and Activate the Conda Environment:**

    ```bash
    conda create -n hr python=3.12  # Create an environment named 'hr'
    conda activate hr             # Activate the environment
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up OpenAI API Key:**

    *   Create a `.env` file in the `hr_interviewer` directory.
    *   Add your OpenAI API key to the `.env` file:

        ```
        OPENAI_API_KEY=your_openai_api_key_here
        ```

## Usage

1.  **Run the Application:**

    ```bash
    python app.py
    ```

    This will launch the Gradio interface in your default web browser.

2.  **Upload a Document:**

    *   Go to the "Upload Document" tab.
    *   Click "Browse" and select the document you want to use as the knowledge base for the interview (e.g., a job description, company information document).

3.  **Select User Role:**

    *   Choose "Candidate" to participate in the interview.
    *   Choose "Admin" and enter the password (`password1`) to access settings and other admin features.

4.  **Start the Interview:**

    *   Click the "Start Interview" button.

5.  **Interact with the Interviewer:**

    *   You can either type your responses or use your microphone to speak.
    *   The AI interviewer will ask questions based on the uploaded document and your previous answers.

6.  **End of Interview and Report:**

    *   After a set number of questions (default is 5), the interview will conclude.
    *   A report will be generated automatically and displayed on the screen.
    *   You can download the report as a DOCX file.

## What to Expect

The AI HR Interviewer will guide you through a simulated interview process. It will ask you questions relevant to the job description or other document you provide. The questions are generated dynamically using RAG, so each interview will be somewhat unique.

The final report provides an assessment of the interview, including:

*   **Candidate Overview:** Basic information about the candidate (if provided during the interview).
*   **Assessment Summary:** Strengths, weaknesses, and overall suitability for the role.
*   **Experience and Skills:** Relevant experience, skills demonstrated, and alignment with job requirements.
*   **Responses:** Observations on communication skills, problem-solving abilities, and behavioral traits.
*   **Recommendations:** Suggested next steps (e.g., further interviews, assessments) and potential training or development needs.

**Note:** The AI interviewer is designed to assist in the interview process, but it should not be the sole basis for hiring decisions. Human judgment and evaluation are still essential.

## Admin Features

*   **Settings:**
    *   **Enable Audio:** Toggle audio input/output.
    *   **Select Interviewer:** Choose between "alloy" and "onyx" voices.
*   **Upload Document:** (Same as described above)
*   **Description:** View a description of the project and a diagram illustrating the system architecture.

## Troubleshooting

*   **Error: No document uploaded:** Make sure you upload a document before starting the interview.
*   **Audio not working:** Ensure your microphone and speakers are properly configured. Check browser permissions for microphone access.
*   **Other errors:** If you encounter any other errors, check the console output for details. You may need to install missing dependencies or restart the application.

## Contributing

Contributions to this project are welcome! Feel free to submit pull requests or open issues to suggest improvements or report bugs.
```

**Remember to:**

*   Replace `<repository_url>` with the actual URL of your Git repository.
*   Consider adding a screenshot or GIF of the application in action to the `README.md`.
*   If you add a `questionnaire.csv` file, mention its purpose in the `README.md` (e.g., "The `questionnaire.csv` file contains optional predefined questions that can supplement the RAG-based question generation.").

This detailed `README.md` will help users understand, set up, and use your AI HR Interviewer effectively. Let me know if you have any other questions.
