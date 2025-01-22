from typing import List, Tuple
import math

def split_text_into_chunks(text: str, chunk_size: int) -> List[str]:
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


def distribute_questions_across_chunks(n_chunks: int, n_questions: int) -> List[int]:
    """
    Distributes a specified number of questions across a specified number of chunks.
    """
    # Initial allocation of at least one question to early chunks if possible
    questions_per_chunk = [1] * min(n_chunks, n_questions)

    remaining_questions = n_questions - len(questions_per_chunk)

    # Distribute remaining questions evenly across chunks
    if remaining_questions > 0:
        for i in range(len(questions_per_chunk)):
            if remaining_questions == 0:
                break
            questions_per_chunk[i] += 1
            remaining_questions -= 1

    # If chunks remain, add zeros to match the total chunks.
    while len(questions_per_chunk) < n_chunks:
        questions_per_chunk.append(0)

    return questions_per_chunk


def generate_questions_for_text(text: str, chunk_size: int, n_questions: int) -> List[Tuple[str, int]]:
    """
    Splits the text into chunks, distributes questions across them, and returns a list of
    (chunk, number of questions).
    """
    chunks = split_text_into_chunks(text, chunk_size)
    n_chunks = len(chunks)

    questions_distribution = distribute_questions_across_chunks(n_chunks, n_questions)

    return list(zip(chunks, questions_distribution))


# Example usage
text = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin hendrerit urna "
    "vel erat bibendum, eget condimentum ipsum interdum. Nulla facilisi. Quisque dictum "
    "eros eu velit varius, eget faucibus mauris euismod. Etiam placerat nisi at urna maximus "
    "viverra. Integer ut odio nec justo volutpat varius ut quis quam. Suspendisse potenti. "
    "Donec vulputate quam quis metus sagittis, sed commodo justo ultricies. Nam ut velit "
    "finibus, venenatis eros vel, consectetur arcu. Praesent vulputate at ligula non elementum. "
    "Nulla varius condimentum justo, non placerat nisl ullamcorper eu."
)

chunk_size = 100  # Max length of each chunk in characters
n_questions = 5   # Total number of questions to be asked

result = generate_questions_for_text(text, chunk_size, n_questions)

for i, (chunk, num_questions) in enumerate(result):
    print(f"Chunk {i + 1} ({len(chunk.split())} words):")
    print(f"Questions: {num_questions}")
    print(chunk)
    print("-" * 40)
