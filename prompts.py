class Prompts:

    @staticmethod
    def generate_paper_summary_prompt(paper_title, content):
        return f'''
        **Instructions:** Analyze the provided paper to generate a JSON response in the following structure:
        {{
        "paperTitle": "{paper_title}",
        "summary": ["A concise overview of the paper (a few sentences)"],
        "abstract": ["Summarizes the paper's central focus and main arguments"],
        "keyFindings": ["Highlights the most important results and conclusions"],
        "methods": ["Briefly outlines the research methods used"],
        "implications": ["Discusses the significance and potential applications of the findings"],
        "conclusion": "Summarizes the key takeaways and possible future directions",
        "insights": ["Insight 1", "Insight 2", "Insight 3"]
        }}
        **Context:** {content}
        '''

    @staticmethod
    def generate_summary_prompt(content):
        return f'''
        **Instructions for Scientists and Professionals:**
        Analyze the provided paper content and generate a structured analysis with the following sections:
        1. Paper Title
        2. Key Findings
        3. Summary
        4. Methods Used
        5. Significance and Implications of Findings
        6. Conclusion
        7. Additional Insights
        8. Real-World Implementations of the Findings

        **Context:** {content}
        '''

    @staticmethod
    def generate_comparison_prompt(combined_key_findings):
        return f'''
        **Task for Scientists and Professionals:**
        Compare and analyze the key findings from the provided papers. Structure your comparison using the following sections:
        1. Summary of Key Findings
        2. Comparisons Between Papers
        3. Insights Gained
        4. Detailed Comparative Analysis
        5. Possible Real-World Implementations for Each Paper

        **Key Findings from Papers:**

        {combined_key_findings}

        **Objective:**
        Provide a structured comparison and analysis that highlights the similarities, differences, and overall contributions of the papers to their respective fields. Ensure that comparisons mention each paper by its title, and include a real-world implementation section for each paper.
        '''

    @staticmethod
    def generate_summary_query_prompt(query):
        return f'''
        **Instructions:**
        1. Provide a concise and informative summary of the input provided.
        2. Structure the summary into short, readable paragraphs.
        3. Use bullet points or numbered lists where appropriate to enhance clarity.
        4. Ensure the summary is clear, well-structured, and covers the main points.
        5. **Limit the summary to no more than 900 characters.**

        **Context:** {query}
        '''

    @staticmethod
    def generate_paper_comparison_prompt(summaries):
        combined_text = "\n\n".join(summaries)
        return f'''
        You are provided with multiple research papers' summaries. Please provide the following:

        1. Overall summary of the papers.
        2. Similarities between the papers.
        3. Differences between the papers.

        Here are the summaries:
        {combined_text}
        '''

    @staticmethod
    def generate_key_findings_comparison_prompt(combined_key_findings):
        return f'''
        **Task for Scientists and Professionals:**
        Compare and analyze the key findings from the provided papers. Generate a JSON response with the following structure:
        {{
            "KeyFindingsSummary": "Summarize the key findings from all the papers collectively, mentioning each paper by title",
            "KeyComparisons": ["List and explain the comparisons between the key findings of the papers, referencing the paper titles"],
            "Insights": ["Highlight key insights that can be drawn from the comparisons"],
            "ComparativeAnalysis": "Provide a detailed comparative analysis of the papers' key findings and their significance to the scientific or professional field",
            "Implementation": ["Describe possible implementations or real-world applications of the findings for each paper"]
        }}

        **Key Findings from Papers:**

        {combined_key_findings}

        **Objective:**
        Provide a structured comparison and analysis in JSON format that highlights the similarities, differences, and overall contributions of the papers to the scientific or professional field. Ensure each comparison references the paper by title, and include an implementation section for each paper.
        '''
