def bot_response(history):
    if not interview_state.interview_history:
        
        reset_interview_action(interview_state.selected_interviewer)

    if interview_state.interview_history[-1]["role"] == "user":
        interview_state.question_count += 1

    
    voice = interview_state.get_voice_setting()
    
    if interview_state.question_count > interview_state.n_of_questions:
        response = "That's all for now. Thank you for your time!"
        interview_state.interview_finished = True

    else:
        # Select prompts based on interview type
        if interview_state.interview_type == "hr":
            if not interview_state.knowledge_retrieval_setup:
                response = get_default_hr_questions(
                    interview_state.question_count
                )
            else:
                if interview_state.question_count == 1:
                    response = get_initial_question(
                        interview_state.interview_chain
                    )
                else:
                    response = get_next_response(
                        interview_state.interview_chain,
                        interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                        [
                            msg["content"]
                            for msg in interview_state.interview_history
                            if msg.get("role") == "user"
                        ],
                        interview_state.question_count,
                    )
        elif interview_state.interview_type == "sarah":
            response = get_next_response(
                interview_state.interview_chain,
                interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                [
                    msg["content"]
                    for msg in interview_state.interview_history
                    if msg.get("role") == "user"
                            ],
                            interview_state.question_count,
                        )
                    elif interview_state.interview_type == "aaron":
                        response = get_next_response(
                            interview_state.interview_chain,
                            interview_state.interview_history[-1]["content"] if interview_state.interview_history[-1]["role"] == "user" else "",
                            [
                                msg["content"]
                                for msg in interview_state.interview_history
                                if msg.get("role") == "user"
                            ],
                            interview_state.question_count,
                        )

                    else:
                        response = "Invalid interview type."

                audio_buffer = BytesIO()
                convert_text_to_speech(response, audio_buffer, voice)
                audio_buffer.seek(0)
                with tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                ) as temp_file:
                    temp_audio_path = temp_file.name
                    temp_file.write(audio_buffer.getvalue())
                interview_state.temp_audio_files.append(temp_audio_path)

                
                history.append({"role": "assistant", "content": response})
                interview_state.interview_history.append({"role": "assistant", "content": response})

                if interview_state.interview_finished:
                    
                    conclusion_message = "Thank you for being here. We will review your responses and provide feedback soon."
                    history.append(
                        {"role": "system", "content": conclusion_message}
                    )
                    interview_state.interview_history.append({"role": "system", "content": conclusion_message})

                    txt_path = save_interview_history(
                        [msg["content"] for msg in history if msg["role"] != "system"], interview_state.language
                    )
                    if txt_path:
                        return (
                            history,
                            gr.Audio(
                                value=temp_audio_path,
                                autoplay=True,
                                visible=True,
                            ),
                            gr.File(visible=True, value=txt_path),
                            gr.Textbox(interactive=False)
                        )
                    else:
                        return (
                            history,
                            gr.Audio(
                                value=temp_audio_path,
                                autoplay=True,
                                visible=True,
                            ),
                            None,
                            gr.Textbox(interactive=False)
                        )

                return (
                    history,
                    gr.Audio(
                        value=temp_audio_path, autoplay=True, visible=True
                    ),
                    None,
                    gr.Textbox(interactive=True)
                )