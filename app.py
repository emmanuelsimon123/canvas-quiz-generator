import streamlit as st
from generate_questions import generate_questions
from build_qti import build_qti_zip
from graph_generator import generate_graph
from PIL import Image
import os
import tempfile

st.set_page_config(page_title="Canvas Quiz Generator", page_icon="📝", layout="centered")

st.title("📝 Canvas Quiz Generator")
st.write("Upload an image of study material and get a Canvas-ready quiz file!")

st.divider()

# Settings
col1, col2 = st.columns(2)
with col1:
    num_questions = st.slider("Number of questions", min_value=1, max_value=20, value=5)
with col2:
    quiz_title = st.text_input("Quiz title", value="My Quiz")

# Question type mode
type_mode = st.radio(
    "How should question types be selected?",
    options=["auto_mix", "one_type", "pick_and_choose"],
    format_func=lambda x: {
        "auto_mix": "🤖 Auto Mix — AI picks the best variety",
        "one_type": "🔘 One Type — All questions are the same type",
        "pick_and_choose": "🎯 Pick & Choose — You select which types to include"
    }[x],
    horizontal=True
)

TYPE_OPTIONS = {
    "multiple_choice": "🔘 Multiple Choice",
    "true_false": "✅ True / False",
    "fill_in_the_blank": "✏️ Fill in the Blank",
    "multiple_answers": "☑️ Multiple Answers",
    "numerical": "🔢 Numerical Answer"
}

selected_single = None
selected_multi = None

if type_mode == "one_type":
    selected_single = st.selectbox(
        "Choose question type",
        options=list(TYPE_OPTIONS.keys()),
        format_func=lambda x: TYPE_OPTIONS[x]
    )

elif type_mode == "pick_and_choose":
    selected_multi = st.multiselect(
        "Choose which types to include",
        options=list(TYPE_OPTIONS.keys()),
        format_func=lambda x: TYPE_OPTIONS[x],
        default=["multiple_choice", "true_false"]
    )
    if not selected_multi:
        st.warning("Please select at least one question type.")

# Graph toggle
include_graphs = st.checkbox("📊 Include graph questions (great for algebra & pre-calc)")

st.divider()

# Upload
uploaded_files = st.file_uploader(
    "Upload image(s) of study material",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader("📸 Uploaded Images")
    cols = st.columns(min(len(uploaded_files), 3))
    for i, file in enumerate(uploaded_files):
        with cols[i % 3]:
            st.image(file, use_container_width=True)

    can_generate = True
    if type_mode == "pick_and_choose" and not selected_multi:
        can_generate = False

    if can_generate and st.button("🚀 Generate Quiz", type="primary", use_container_width=True):
        all_questions = {"questions": []}

        if type_mode == "auto_mix":
            q_type = "auto_mix"
            q_selected = None
        elif type_mode == "one_type":
            q_type = selected_single
            q_selected = None
        else:
            q_type = "pick_and_choose"
            q_selected = selected_multi

        for file in uploaded_files:
            with st.spinner(f"Reading {file.name}..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(file.getvalue())
                    tmp_path = tmp.name

                try:
                    result = generate_questions(
                        tmp_path,
                        num_questions=num_questions,
                        question_type=q_type,
                        selected_types=q_selected,
                        include_graphs=include_graphs
                    )
                    all_questions["questions"].extend(result["questions"])
                except Exception as e:
                    st.error(f"Error processing {file.name}: {str(e)}")
                finally:
                    os.unlink(tmp_path)

        if all_questions["questions"]:
            # Generate graph images
            graph_images = {}
            for i, q in enumerate(all_questions["questions"]):
                if "graph" in q:
                    with st.spinner(f"Generating graph for Q{i+1}..."):
                        try:
                            graph_images[i] = generate_graph(q["graph"])
                        except Exception as e:
                            st.warning(f"Could not generate graph for Q{i+1}: {str(e)}")

            st.subheader("📋 Generated Questions")

            for i, q in enumerate(all_questions["questions"]):
                q_type_label = q.get("type", "multiple_choice")
                type_labels = {
                    "multiple_choice": "🔘 MC",
                    "true_false": "✅ T/F",
                    "fill_in_the_blank": "✏️ FIB",
                    "multiple_answers": "☑️ MA",
                    "numerical": "🔢 NUM"
                }
                label = type_labels.get(q_type_label, "❓")
                has_graph = "📊" if i in graph_images else ""

                with st.expander(f"Q{i+1} [{label}] {has_graph}: {q['question'][:80]}"):

                    # Show graph if exists
                    if i in graph_images:
                        import base64
                        graph_bytes = base64.b64decode(graph_images[i])
                        st.image(graph_bytes, caption="Graph shown to students")

                    if q_type_label == "multiple_choice":
                        for letter, text in q["options"].items():
                            if letter == q.get("correct_answer"):
                                st.write(f"**✅ {letter}: {text}**")
                            else:
                                st.write(f"⬜ {letter}: {text}")

                    elif q_type_label == "true_false":
                        correct = q.get("correct_answer", "")
                        for val in ["True", "False"]:
                            if val == correct:
                                st.write(f"**✅ {val}**")
                            else:
                                st.write(f"⬜ {val}")

                    elif q_type_label == "fill_in_the_blank":
                        answers = q.get("correct_answers", [])
                        st.write(f"**✅ Accepted answers:** {', '.join(answers)}")

                    elif q_type_label == "multiple_answers":
                        correct_list = q.get("correct_answers", [])
                        for letter, text in q["options"].items():
                            if letter in correct_list:
                                st.write(f"**✅ {letter}: {text}**")
                            else:
                                st.write(f"⬜ {letter}: {text}")

                    elif q_type_label == "numerical":
                        ans = q.get("correct_answer", "")
                        margin = q.get("margin", 0)
                        st.write(f"**✅ Correct answer:** {ans}")
                        if margin > 0:
                            st.write(f"**± Margin:** {margin}")

            st.divider()
            zip_file = build_qti_zip(all_questions, quiz_title=quiz_title, graph_images=graph_images)

            st.download_button(
                label="📥 Download Canvas Quiz File (.zip)",
                data=zip_file,
                file_name=f"{quiz_title.replace(' ', '_')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

            st.info("**How to import:** Canvas → Course → Settings → Import Course Content → QTI .zip file → Upload this file")