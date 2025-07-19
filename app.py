import os
import gradio as gr
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO
import datetime
# Global variable to hold the uploaded dataframe
uploaded_df = None
desc_col_global = None
cost_col_global = None
date_col_global = None

def load_excel(file):
    global uploaded_df, desc_col_global, cost_col_global, date_col_global

    try:
        # Read all sheets if it's a multi-sheet file
        xls = pd.read_excel(file, engine="openpyxl", sheet_name=None)
    except:
        xls = pd.read_excel(file, sheet_name=None)

    combined_df = pd.DataFrame()
    for sheet_name, df in xls.items():
        # Normalize columns
        df.columns = df.columns.str.strip().str.lower()

        # Identify columns
        cost_col = next((col for col in df.columns if 'value' in col or 'amount' in col), None)
        date_col = next((col for col in df.columns if 'date' in col), None)
        possible_desc_cols = ['item descriptor', 'item name', 'item description', 'chemical', 'description']
        desc_col = next((col for col in df.columns if col in possible_desc_cols), None)

        if not all([cost_col, date_col, desc_col]):
            continue

        # Clean and parse
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[cost_col, desc_col, date_col])

        # Optionally tag the sheet
        df['sheet'] = sheet_name

        combined_df = pd.concat([combined_df, df], ignore_index=True)

    if combined_df.empty:
        return gr.update(choices=[]), (
            "❌ No valid sections found.\n\nMake sure at least one sheet has:\n"
            "- A date column (e.g., 'Date')\n"
            "- A cost column (e.g., 'Amount' or 'Value')\n"
            "- A chemical name column (e.g., 'Item Descriptor', 'Item Name', or 'Chemical')"
        )

    # Store globally
    uploaded_df = combined_df
    desc_col_global = desc_col
    cost_col_global = cost_col
    date_col_global = date_col

    chemicals = sorted(combined_df[desc_col].dropna().unique())
    return gr.update(choices=chemicals, value=chemicals[0]), "✅ File uploaded successfully (merged multiple sections)!"

def load_second_excel(file):
    if file is None:
        return "📭 Second file removed."
    try:
        xls = pd.read_excel(file, engine="openpyxl", sheet_name=None)
    except:
        xls = pd.read_excel(file, sheet_name=None)

    for sheet_name, df in xls.items():
        df.columns = df.columns.str.strip().str.lower()

        cost_col = next((col for col in df.columns if 'value' in col or 'amount' in col), None)
        date_col = next((col for col in df.columns if 'date' in col), None)
        possible_desc_cols = ['item descriptor', 'item name', 'item description', 'chemical', 'description']
        desc_col = next((col for col in df.columns if col in possible_desc_cols), None)

        if all([cost_col, date_col, desc_col]):
            return "✅ Second file uploaded and looks good!"

    return (
        "❌ Could not find valid data in second file.\n\nMake sure it has:\n"
        "- A date column (e.g., 'Date')\n"
        "- A cost column (e.g., 'Amount' or 'Value')\n"
        "- A chemical name column (e.g., 'Item Name', 'Description')"
    )

def generate_report(chemicals, start_date, end_date, comparison_type):
    if uploaded_df is None:
        return "⚠ Please upload a file first.", None

    df = uploaded_df

    # Filter by multiple chemicals
    mask = df[desc_col_global].str.strip().str.lower().isin([chem.strip().lower() for chem in chemicals])
    df_filtered = df[mask &
        (df[date_col_global] >= pd.to_datetime(start_date)) &
        (df[date_col_global] <= pd.to_datetime(end_date))]



    if df_filtered.empty:
        sample = df[[desc_col_global, date_col_global]].drop_duplicates().head()
        return (
            f"⚠ No data found for *{', '.join(chemicals)}* between {start_date} and {end_date}.\n\n"
            f"🔍 Sample data:\n{sample.to_markdown(index=False)}",
            None
        )

    try:
        if comparison_type == "Month-wise":
            df_filtered['Month'] = df_filtered[date_col_global].dt.strftime('%b')
            df_filtered['Year'] = df_filtered[date_col_global].dt.year
            month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            df_filtered['Month'] = pd.Categorical(df_filtered['Month'], categories=month_order, ordered=True)
            df_grouped = df_filtered.groupby(['Year', 'Month'])[cost_col_global].sum().reset_index()
            df_grouped.rename(columns={cost_col_global: 'Total Cost'}, inplace=True)

            fig = px.line(df_grouped, x='Month', y='Total Cost', color='Year',
                          markers=True, title=f"Month-wise Cost for {', '.join(chemicals)} (Colored by Year)")

            try:
                total_cost = df_grouped['Total Cost'].sum()
                data_points = len(df_grouped)

                top_month_row = df_grouped.loc[df_grouped['Total Cost'].idxmax()]
                top_month = f"{top_month_row['Month']} {top_month_row['Year']}"
                top_cost = top_month_row['Total Cost']

                report = (
                    f"📊 *Month-wise Report*\n\n"
                    f"- Selected chemicals: *{', '.join(chemicals)}*\n"
                    f"- Date range: {start_date} to {end_date}\n"
                    f"- Highest month: *{top_month}* with ₹{top_cost:.2f}\n"
                    f"- Total cost (all months): ₹{total_cost:.2f}\n"
                    f"- Total data points: {data_points}"
                )
            except Exception as e:
                report = f"ℹ Chart generated, but summary failed: {str(e)}"


        elif comparison_type == "Year-wise":
            df_filtered['Month'] = df_filtered[date_col_global].dt.strftime('%b')
            df_filtered['Year'] = df_filtered[date_col_global].dt.year
            month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            df_filtered['Month'] = pd.Categorical(df_filtered['Month'], categories=month_order, ordered=True)
            df_grouped = df_filtered.groupby(['Year', 'Month'])[cost_col_global].sum().reset_index()
            df_grouped.rename(columns={cost_col_global: 'Total Cost'}, inplace=True)

            # 🎨 Dynamic year color map
            unique_years = sorted(df_grouped['Year'].unique())
            color_list = ['green', 'red', 'blue', 'orange', 'purple', 'brown']
            year_color_map = {year: color_list[i % len(color_list)] for i, year in enumerate(unique_years)}

            fig = px.line(df_grouped, x='Month', y='Total Cost', color='Year',
                          markers=True, title=f"Monthly Cost Comparison Between Years for {', '.join(chemicals)}",
                          color_discrete_map=year_color_map)

            try:
                total_cost = df_grouped['Total Cost'].sum()
                data_points = len(df_grouped)

                yearly_total = df_grouped.groupby("Year")['Total Cost'].sum()
                top_year = yearly_total.idxmax()
                top_cost = yearly_total.max()

                breakdown = "\n".join([f"  - {year}: ₹{cost:.2f}" for year, cost in yearly_total.items()])

                report = (
                    f"📊 *Year-wise Report*\n\n"
                    f"- Selected chemicals: *{', '.join(chemicals)}*\n"
                    f"- Date range: {start_date} to {end_date}\n"
                    f"- Year with highest cost: *{top_year}* (₹{top_cost:.2f})\n"
                    f"- Total cost (all years): ₹{total_cost:.2f}\n"
                    f"- Total data points: {data_points}\n"
                    f"- Breakdown:\n{breakdown}"
                )
            except Exception as e:
                report = f"ℹ Chart generated, but summary failed: {str(e)}"


        else:
            df_filtered['Date'] = df_filtered[date_col_global].dt.date
            df_grouped = df_filtered.groupby(['Date', desc_col_global])[cost_col_global].sum().reset_index()
            df_grouped['Date'] = pd.to_datetime(df_grouped['Date'])
            df_grouped.rename(columns={desc_col_global: 'Chemical', cost_col_global: 'Total Cost'}, inplace=True)

            fig = px.line(
                df_grouped,
                x='Date',
                y='Total Cost',
                color='Chemical',
                title=f"Cost Trend by Chemical",
                markers=True
            )

    except Exception as e:
        return f"⚠ Graph generation failed: {str(e)}", None

    # ✅ Build report based on grouping
    try:
          total_by_chemical = df_grouped.groupby('Chemical')['Total Cost'].sum().sort_values(ascending=False)
          top_chem = total_by_chemical.idxmax()
          top_cost = total_by_chemical.max()

          report = (
              f"📊 *Summary Report*\n\n"
              f"- Selected chemicals: *{', '.join(chemicals)}*\n"
              f"- Date range: {start_date} to {end_date}\n"
              f"- Highest overall cost: *₹{top_cost:.2f}* by *{top_chem}*\n"
              f"- Total cost (all chemicals): ₹{df_grouped['Total Cost'].sum():.2f}\n"
              f"- Total data points: {len(df_grouped)}"
          )

    except Exception as e:
        report = f"ℹ Chart generated, but report summary failed: {str(e)}"

    return report, fig
def trigger_report(chemicals, start, end, comparison_type):
    # 👇 Defensive: Ensure chemicals is a list of strings
    if not chemicals or not isinstance(chemicals, list) or len(chemicals) == 0:
        return "⚠ Please select at least one chemical.", None

    try:
        return generate_report(chemicals, start, end, comparison_type)
    except Exception as e:
        return f"❌ Error while generating report: {str(e)}", None

#Compare Function
def compare_files_multi_chemical(file1, file2, chemicals, start_date, end_date):
    if file1 is None or file2 is None:
        return "⚠ Please upload both files before comparing.", None

    def read_and_process(file, label):
        try:
            df = pd.read_excel(file, engine="openpyxl")
        except:
            df = pd.read_excel(file)

        df.columns = df.columns.str.strip().str.lower()
        cost_col = next((col for col in df.columns if 'value' in col or 'amount' in col), None)
        date_col = next((col for col in df.columns if 'date' in col), None)
        desc_col = next((col for col in df.columns if col in ['item description', 'item name', 'chemical', 'description']), None)

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[cost_col, date_col, desc_col])

        chemical_list = [chem.strip().lower() for chem in chemicals]
        df = df[df[desc_col].str.strip().str.lower().isin(chemical_list)]

        df = df[(df[date_col] >= pd.to_datetime(start_date)) & (df[date_col] <= pd.to_datetime(end_date))]

        df['Chemical'] = df[desc_col]  # Keep original chemical names for labeling
        df_grouped = df.groupby([df[date_col].dt.date, 'Chemical'])[cost_col].sum().reset_index()
        df_grouped.columns = ['Date', 'Chemical', 'Total Cost']
        df_grouped['Source'] = label
        return df_grouped

    try:
        df1 = read_and_process(file1, "File 1")
        df2 = read_and_process(file2, "File 2")
        combined = pd.concat([df1, df2])
        combined['Date'] = pd.to_datetime(combined['Date'])

        # Plot
        fig = px.line(
            combined,
            x='Date',
            y='Total Cost',
            color='Source',
            line_dash='Chemical',
            title=f"Cost Trend Comparison for {', '.join(chemicals)}",
            markers=True
        )

        try:
            # Total per file
            total_cost_file1 = df1['Total Cost'].sum()
            total_cost_file2 = df2['Total Cost'].sum()

            # Top chemical per file
            top_chem_file1 = df1.groupby('Chemical')['Total Cost'].sum().sort_values(ascending=False)
            top_chem_name_1 = top_chem_file1.idxmax()
            top_chem_value_1 = top_chem_file1.max()

            top_chem_file2 = df2.groupby('Chemical')['Total Cost'].sum().sort_values(ascending=False)
            top_chem_name_2 = top_chem_file2.idxmax()
            top_chem_value_2 = top_chem_file2.max()

            report = (
                f"📊 *Comparison Summary for {', '.join(chemicals)}*\n\n"
                f"🔹 *File 1:*\n"
                f"  - Total cost: ₹{total_cost_file1:.2f}\n"
                f"  - Top chemical: *{top_chem_name_1}* (₹{top_chem_value_1:.2f})\n\n"
                f"🔹 *File 2:*\n"
                f"  - Total cost: ₹{total_cost_file2:.2f}\n"
                f"  - Top chemical: *{top_chem_name_2}* (₹{top_chem_value_2:.2f})\n\n"
                f"📈 Trend plotted by date for visual comparison."
            )
        except Exception as e:
            report = f"ℹ Chart generated, but comparison summary failed: {str(e)}"


        return report, fig

    except Exception as e:
        return f"⚠ Comparison failed: {str(e)}", None

# Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("## 🧪 Agrochemical Cost Analyzer\nUpload an Excel file to begin.")

    with gr.Row():
        file_input = gr.File(label="Upload Excel File (.xlsx)", type='binary')
        status_output = gr.Textbox(label="Upload Status", interactive=False)
        #second_file_input = gr.File(label="Upload Second Excel File (Optional for Comparison)", type='binary')


    add_second_file_button = gr.Button("➕ Add Second File")

    with gr.Column(visible=False) as second_file_section:
        second_file_input = gr.File(label="Upload Second Excel File", type='binary')
        second_file_status_output = gr.Textbox(label="Upload Status", interactive=False)

    def show_second_file_input():
        return gr.update(visible=True), gr.update(visible=True)

    add_second_file_button.click(
        show_second_file_input,
        outputs=[second_file_section, second_file_status_output]
    )

    chemical_dropdown = gr.Dropdown(
        label="Select Chemicals",
        choices=[],
        multiselect=True,
        interactive=True
    )


    with gr.Row():
        start_input = gr.Textbox(label="Start Date (YYYY-MM-DD)", value="2020-01-01")
        end_input = gr.Textbox(label="End Date (YYYY-MM-DD)", value="2020-12-31")


    comparison_type_dropdown = gr.Dropdown(
      label="Comparison Type",
      choices=["None", "Month-wise", "Year-wise"],
      value="None",
      interactive=True
    )

    compare_button = gr.Button("Compare Chemical in Both Files", visible=False)
    def show_compare_button(file):
      return gr.update(visible=file is not None)

    #Restart
    reset_button = gr.Button("🔄 Restart & Upload New File")

    #Restart only the filters
    reset_filters_button = gr.Button("🔁 Reset Filters Only")

  # Full reset (also clears uploaded files)
    def reset_app():
        global uploaded_df, desc_col_global, cost_col_global, date_col_global
        uploaded_df = None
        desc_col_global = None
        cost_col_global = None
        date_col_global = None

        return (
            gr.update(value=None),  # file_input
            gr.update(value=None),  # second_file_input
            gr.update(choices=[], value=[]),  # chemical_dropdown
            "📭 Upload a file to begin.",  # status_output
            "📭 Upload a file to begin.",  # second_file_status_output
            gr.update(value="2020-01-01"),  # start_input
            gr.update(value="2020-12-31"),  # end_input
            gr.update(value="None"),  # comparison_type_dropdown
            "",  # report_output
            None,  # plot_output
            gr.update(visible=False),  # second_file_section (hide after reset)
            gr.update(visible=False)   # compare_button (hide after reset)
        )


    # Filters-only reset (keeps uploaded files)
    def reset_filters_only():
        return (
            gr.update(value=[]),  # Reset chemical selection
            gr.update(value="2020-01-01"),  # Reset start date
            gr.update(value="2020-12-31"),  # Reset end date
            gr.update(value="None"),  # Reset comparison type
            "",  # Clear report output
            None  # Clear graph
        )


    report_output = gr.Markdown()
    plot_output = gr.Plot()

    #Linking this button
    compare_button.click(
      compare_files_multi_chemical,
      inputs=[file_input, second_file_input, chemical_dropdown, start_input, end_input],
      outputs=[report_output, plot_output]
    )

    #Linking the Restart Button
    reset_button.click(
        reset_app,
        inputs=[],
        outputs=[
            file_input, second_file_input,
            chemical_dropdown, status_output,
            start_input, end_input,
            comparison_type_dropdown,
            report_output, plot_output
        ]
    )

    #Linking the filter restart button
    reset_filters_button.click(
        reset_filters_only,
        inputs=[],
        outputs=[
            chemical_dropdown,
            start_input,
            end_input,
            comparison_type_dropdown,
            report_output,
            plot_output
        ]
    )


    second_file_input.change(show_compare_button, inputs=second_file_input, outputs=compare_button)
    second_file_input.change(
        load_second_excel,
        inputs=second_file_input,
        outputs=second_file_status_output
    )

    file_input.change(load_excel, inputs=file_input, outputs=[chemical_dropdown, status_output])
    chemical_dropdown.change(trigger_report, inputs=[chemical_dropdown, start_input, end_input, comparison_type_dropdown], outputs=[report_output, plot_output])
    start_input.change(trigger_report, inputs=[chemical_dropdown, start_input, end_input, comparison_type_dropdown], outputs=[report_output, plot_output])
    end_input.change(trigger_report, inputs=[chemical_dropdown, start_input, end_input, comparison_type_dropdown], outputs=[report_output, plot_output])
    comparison_type_dropdown.change(trigger_report, inputs=[chemical_dropdown, start_input, end_input, comparison_type_dropdown], outputs=[report_output, plot_output])


demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))