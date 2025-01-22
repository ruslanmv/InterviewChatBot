import os
import fitz  # PyMuPDF for PDF handling
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema import Document, StrOutputParser
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains import RetrievalQA
from langchain.chains.llm import LLMChain
from langchain_core.runnables import RunnablePassthrough
from prompt_instructions import get_interview_prompt_hr, get_report_prompt_hr

# Function to load documents based on file type
def load_document(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [Document(page_content=text, metadata={"source": file_path})]
    elif ext == ".pdf":
        try:
            with fitz.open(file_path) as pdf:
                text = ""
                for page in pdf:
                    text += page.get_text()
            return [Document(page_content=text, metadata={"source": file_path})]
        except Exception as e:
            raise RuntimeError(f"Error loading PDF file: {e}")
    else:
        raise RuntimeError(f"Unsupported file format: {ext}")

# Function to set up knowledge retrieval
def setup_knowledge_retrieval(llm, language='english', file_path=None):
    embedding_model = OpenAIEmbeddings()

    if file_path:
        # Load and split the document
        documents = load_document(file_path)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)

        # Create a new FAISS index from the document
        faiss_index_path = "knowledge/faiss_index_hr_documents"
        try:
            documents_faiss_index = FAISS.from_documents(texts, embedding_model)
            documents_faiss_index.save_local(faiss_index_path)
            print(f"New FAISS vector store created and saved at {faiss_index_path}")
        except Exception as e:
            raise RuntimeError(f"Error during FAISS index creation: {e}")
    else:
        raise RuntimeError("No document provided for knowledge retrieval setup.")

    documents_retriever = documents_faiss_index.as_retriever()

    # Prompt template for the interview
    interview_prompt_template = """
    Use the following pieces of context to answer the question at the end. 
    If you don't know the answer, just say that you don't know, don't try to make up an answer. 
    Keep the answer as concise as possible.
    {context}
    Question: {question}
    Helpful Answer:"""
    interview_prompt = PromptTemplate.from_template(interview_prompt_template)

    # Prompt template for the report
    report_prompt_template = """
    Use the following pieces of context to generate a report at the end. 
    If you don't know the answer, just say that you don't know, don't try to make up an answer. 
    Keep the answer as concise as possible.
    {context}
    Question: {question}
    Helpful Answer:"""
    report_prompt = PromptTemplate.from_template(report_prompt_template)

    # Create RetrievalQA chains
    interview_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=documents_retriever,
        chain_type_kwargs={"prompt": interview_prompt}
    )

    report_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=documents_retriever,
        chain_type_kwargs={"prompt": report_prompt}
    )

    return interview_chain, report_chain, documents_retriever

def get_next_response(interview_chain, message, history, question_count):
    if question_count >= 5:
        return "Thank you for your responses. I will now prepare a report."

    if not interview_chain:
        return "Error: Knowledge base not loaded. Please contact an admin."

    # Generate the next question using RetrievalQA
    response = interview_chain.invoke({"query": message})
    next_question = response.get("result", "Could you provide more details on that?")

    return next_question

def generate_report(report_chain, history, language):
    combined_history = "\n".join(history)

    # If report_chain is not available, return a fallback report
    if not report_chain:
        print("[DEBUG] Report chain not available. Generating a fallback HR report.")
        fallback_report = f"""
        HR Report in {language}:
        Interview Summary:
        {combined_history}

        Assessment:
        Based on the responses, the candidate's strengths, areas for improvement, and overall fit for the role have been noted. No additional knowledge-based insights due to missing vector database.
        """
        return fallback_report

    # Generate report using the retrieval chain
    result = report_chain.invoke({"query": f"Please provide an HR report based on the interview in {language}. Interview history: {combined_history}"})

    return result.get("result", "Unable to generate report due to insufficient information.")

def get_initial_question(interview_chain):
    if not interview_chain:
        return "Please introduce yourself and tell me a little bit about your professional background."

    result = interview_chain.invoke({"query": "What should be the first question in an HR interview?"})
    return result.get("result", "Could you tell me a little bit about yourself and your professional background?")



