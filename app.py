import gradio as gr
import pandas as pd
from datetime import datetime
from utils import read_excel, filter_data, get_cost_usage_plot, generate_report

uploaded_files = []
combined_df = pd.DataFrame()

def upload_files(files):
    global uploaded_files, combined_df
    uploaded_files = files
    dfs = [read_excel(f) for f in files]
    combined_df = pd.concat(dfs, ignore_index=True)
    chemicals = pd.unique(combined_df[["SoE Description", "Sub SoE Description"]].values.ravel("K"))
    chemicals = [chem for chem in chemicals if pd.notnull(chem)]
    return gr.update(choices=chemicals), gr.update(visible=True)

def process_selection(chemical, start, end):
    try:
        start = datetime.strptime(start.strip(), "%Y-%m-%d").date()
        end = datetime.strptime(end.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "❌ Invalid date format. Please use YYYY-MM-DD.", None

    df_filtered = filter_data(combined_df, chemical, start, end)
    if df_filtered.empty:
        return "⚠️ No data found for this selection.", None

    report = generate_report(df_filtered)
    plot = get_cost_usage_plot(df_filtered)
    return report, plot

with gr.Blocks() as demo:
    gr.Markdown("## 📊 Chemical Usage Dashboard")

    with gr.Row():
        file_input = gr.File(file_types=[".xlsx"], file_count="multiple", label="Upload Excel Files")

    main_controls = gr.Column(visible=False)
    with main_controls:
        chem_select = gr.Dropdown(label="Select Chemical", elem_id="chem_select")
        start_date = gr.Textbox(label="Start Date (YYYY-MM-DD)", placeholder="e.g. 2024-01-01")
        end_date = gr.Textbox(label="End Date (YYYY-MM-DD)", placeholder="e.g. 2024-12-31")
        submit = gr.Button("Generate Report")

        report_output = gr.Textbox(label="Summary", lines=4)
        image_output = gr.Image(type="pil")

        submit.click(fn=process_selection,
                     inputs=[chem_select, start_date, end_date],
                     outputs=[report_output, image_output])

    # ✅ This line now references component objects correctly
    file_input.change(fn=upload_files, inputs=file_input, outputs=[chem_select, main_controls])

demo.launch()
