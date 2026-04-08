import xml.etree.ElementTree as ET
import zipfile
import io

def build_qti_zip(questions_data, quiz_title="My Quiz", graph_images=None):
    if graph_images is None:
        graph_images = {}

    root = ET.Element("questestinterop")
    root.set("xmlns", "http://www.imsglobal.org/xsd/ims_qtiasiv1p2")

    assessment = ET.SubElement(root, "assessment", title=quiz_title)
    assessment.set("ident", "quiz_001")

    metadata = ET.SubElement(assessment, "qtimetadata")
    meta_field = ET.SubElement(metadata, "qtimetadatafield")
    ET.SubElement(meta_field, "fieldlabel").text = "qmd_timelimit"
    ET.SubElement(meta_field, "fieldentry").text = ""

    section = ET.SubElement(assessment, "section", ident="section_001")

    for i, q in enumerate(questions_data["questions"]):
        q_type = q.get("type", "multiple_choice")
        graph_b64 = graph_images.get(i, None)

        if q_type == "multiple_choice":
            build_mc(section, q, i, graph_b64)
        elif q_type == "true_false":
            build_tf(section, q, i, graph_b64)
        elif q_type == "fill_in_the_blank":
            build_fib(section, q, i, graph_b64)
        elif q_type == "multiple_answers":
            build_ma(section, q, i, graph_b64)
        elif q_type == "numerical":
            try:
                float(q["correct_answer"])
                build_numerical(section, q, i, graph_b64)
            except (ValueError, TypeError):
                q["correct_answers"] = [str(q["correct_answer"])]
                build_fib(section, q, i, graph_b64)

    xml_string = ET.tostring(root, encoding="unicode", xml_declaration=True)

    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="quiz_manifest">
  <organizations/>
  <resources>
    <resource identifier="res_001" type="imsqti_xmlv1p2" href="quiz.xml">
      <file href="quiz.xml"/>
    </resource>
  </resources>
</manifest>"""

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("quiz.xml", xml_string)
        zf.writestr("imsmanifest.xml", manifest)

    zip_buffer.seek(0)
    return zip_buffer


def add_item_metadata(item, question_type, points="1.0"):
    item_meta = ET.SubElement(item, "itemmetadata")
    qt_meta = ET.SubElement(item_meta, "qtimetadata")

    field1 = ET.SubElement(qt_meta, "qtimetadatafield")
    ET.SubElement(field1, "fieldlabel").text = "question_type"
    ET.SubElement(field1, "fieldentry").text = question_type

    field2 = ET.SubElement(qt_meta, "qtimetadatafield")
    ET.SubElement(field2, "fieldlabel").text = "points_possible"
    ET.SubElement(field2, "fieldentry").text = points


def build_question_html(question_text, graph_b64=None):
    html = f"<p>{question_text}</p>"
    if graph_b64:
        html += f'<p><img src="data:image/png;base64,{graph_b64}" style="max-width:500px;" /></p>'
    return html


def add_question_text(presentation, question_text, graph_b64=None):
    material = ET.SubElement(presentation, "material")
    mattext = ET.SubElement(material, "mattext", texttype="text/html")
    mattext.text = build_question_html(question_text, graph_b64)


def build_mc(section, q, i, graph_b64=None):
    item = ET.SubElement(section, "item", ident=f"item_{i+1}", title=f"Question {i+1}")
    add_item_metadata(item, "multiple_choice_question")

    presentation = ET.SubElement(item, "presentation")
    add_question_text(presentation, q["question"], graph_b64)

    response_lid = ET.SubElement(presentation, "response_lid", ident="response1", rcardinality="Single")
    render_choice = ET.SubElement(response_lid, "render_choice")

    for letter, option_text in q["options"].items():
        response_label = ET.SubElement(render_choice, "response_label", ident=letter)
        mat = ET.SubElement(response_label, "material")
        mt = ET.SubElement(mat, "mattext", texttype="text/html")
        mt.text = f"<p>{option_text}</p>"

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    ET.SubElement(outcomes, "decvar", maxvalue="100", minvalue="0", varname="SCORE", vartype="Decimal")

    respcondition = ET.SubElement(resprocessing, "respcondition", attrib={"continue": "No"})
    conditionvar = ET.SubElement(respcondition, "conditionvar")
    ET.SubElement(conditionvar, "varequal", respident="response1").text = q["correct_answer"]
    ET.SubElement(respcondition, "setvar", action="Set", varname="SCORE").text = "100"


def build_tf(section, q, i, graph_b64=None):
    item = ET.SubElement(section, "item", ident=f"item_{i+1}", title=f"Question {i+1}")
    add_item_metadata(item, "true_false_question")

    presentation = ET.SubElement(item, "presentation")
    add_question_text(presentation, q["question"], graph_b64)

    response_lid = ET.SubElement(presentation, "response_lid", ident="response1", rcardinality="Single")
    render_choice = ET.SubElement(response_lid, "render_choice")

    for val in ["True", "False"]:
        response_label = ET.SubElement(render_choice, "response_label", ident=val)
        mat = ET.SubElement(response_label, "material")
        mt = ET.SubElement(mat, "mattext", texttype="text/plain")
        mt.text = val

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    ET.SubElement(outcomes, "decvar", maxvalue="100", minvalue="0", varname="SCORE", vartype="Decimal")

    respcondition = ET.SubElement(resprocessing, "respcondition", attrib={"continue": "No"})
    conditionvar = ET.SubElement(respcondition, "conditionvar")
    ET.SubElement(conditionvar, "varequal", respident="response1").text = q["correct_answer"]
    ET.SubElement(respcondition, "setvar", action="Set", varname="SCORE").text = "100"


def build_fib(section, q, i, graph_b64=None):
    item = ET.SubElement(section, "item", ident=f"item_{i+1}", title=f"Question {i+1}")
    add_item_metadata(item, "short_answer_question")

    presentation = ET.SubElement(item, "presentation")
    add_question_text(presentation, q["question"], graph_b64)

    response_str = ET.SubElement(presentation, "response_str", ident="response1", rcardinality="Single")
    render_fib = ET.SubElement(response_str, "render_fib")
    ET.SubElement(render_fib, "response_label", ident="answer1", rshuffle="No")

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    ET.SubElement(outcomes, "decvar", maxvalue="100", minvalue="0", varname="SCORE", vartype="Decimal")

    respcondition = ET.SubElement(resprocessing, "respcondition", attrib={"continue": "No"})
    conditionvar = ET.SubElement(respcondition, "conditionvar")

    correct_answers = q.get("correct_answers", [])
    if len(correct_answers) == 1:
        ET.SubElement(conditionvar, "varequal", respident="response1").text = str(correct_answers[0])
    else:
        or_elem = ET.SubElement(conditionvar, "or")
        for ans in correct_answers:
            ET.SubElement(or_elem, "varequal", respident="response1").text = str(ans)

    ET.SubElement(respcondition, "setvar", action="Set", varname="SCORE").text = "100"


def build_ma(section, q, i, graph_b64=None):
    item = ET.SubElement(section, "item", ident=f"item_{i+1}", title=f"Question {i+1}")
    add_item_metadata(item, "multiple_answers_question")

    presentation = ET.SubElement(item, "presentation")
    add_question_text(presentation, q["question"], graph_b64)

    response_lid = ET.SubElement(presentation, "response_lid", ident="response1", rcardinality="Multiple")
    render_choice = ET.SubElement(response_lid, "render_choice")

    for letter, option_text in q["options"].items():
        response_label = ET.SubElement(render_choice, "response_label", ident=letter)
        mat = ET.SubElement(response_label, "material")
        mt = ET.SubElement(mat, "mattext", texttype="text/html")
        mt.text = f"<p>{option_text}</p>"

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    ET.SubElement(outcomes, "decvar", maxvalue="100", minvalue="0", varname="SCORE", vartype="Decimal")

    respcondition = ET.SubElement(resprocessing, "respcondition", attrib={"continue": "No"})
    conditionvar = ET.SubElement(respcondition, "conditionvar")

    and_elem = ET.SubElement(conditionvar, "and")
    for ans in q["correct_answers"]:
        ET.SubElement(and_elem, "varequal", respident="response1").text = ans

    ET.SubElement(respcondition, "setvar", action="Set", varname="SCORE").text = "100"


def build_numerical(section, q, i, graph_b64=None):
    item = ET.SubElement(section, "item", ident=f"item_{i+1}", title=f"Question {i+1}")
    add_item_metadata(item, "numerical_question")

    presentation = ET.SubElement(item, "presentation")
    add_question_text(presentation, q["question"], graph_b64)

    response_str = ET.SubElement(presentation, "response_str", ident="response1", rcardinality="Single")
    render_fib = ET.SubElement(response_str, "render_fib", fibtype="Decimal")
    ET.SubElement(render_fib, "response_label", ident="answer1", rshuffle="No")

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    ET.SubElement(outcomes, "decvar", maxvalue="100", minvalue="0", varname="SCORE", vartype="Decimal")

    respcondition = ET.SubElement(resprocessing, "respcondition", attrib={"continue": "No"})
    conditionvar = ET.SubElement(respcondition, "conditionvar")

    correct = float(q["correct_answer"])
    margin = float(q.get("margin", 0))

    or_elem = ET.SubElement(conditionvar, "or")
    ET.SubElement(or_elem, "varequal", respident="response1").text = str(correct)

    if margin > 0:
        and_elem = ET.SubElement(or_elem, "and")
        ET.SubElement(and_elem, "vargte", respident="response1").text = str(correct - margin)
        ET.SubElement(and_elem, "varlte", respident="response1").text = str(correct + margin)

    ET.SubElement(respcondition, "setvar", action="Set", varname="SCORE").text = "100"