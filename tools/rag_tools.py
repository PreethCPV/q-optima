import os
import re
from crewai.tools import tool

class RAGTools:
    
    @tool("query_quantum_guidelines")
    def query_docs(query: str) -> str:
        """
        Use this tool to read the Qiskit 1.0 guidelines and hardware rules.
        Pass a relevant search term or 'all' to retrieve the entire guideline document.
        Use this BEFORE writing any code. For specific query, it will only return relevant sections, saving token bandwidth.
        """
        docs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "quantum_guidelines.md")
        
        try:
            with open(docs_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if query.lower() == 'all':
                return f"QUANTUM GUIDELINES FULL TEXT:\n\n{content}"
            else:
                # Optimized chunking based on markdown headers
                sections = re.split(r'(^#+\s.*)', content, flags=re.MULTILINE)
                relevant_sections = []
                
                # The first element is pre-header text. Let's group headers with content.
                if sections[0].strip():
                    if query.lower() in sections[0].lower():
                        relevant_sections.append(sections[0])
                        
                for i in range(1, len(sections), 2):
                    header = sections[i]
                    body = sections[i+1] if i+1 < len(sections) else ""
                    if query.lower() in header.lower() or query.lower() in body.lower():
                        relevant_sections.append(header + body)
                        
                if not relevant_sections:
                    return f"No matching guidelines found for '{query}'. Providing full text instead:\n\n{content}"
                
                joined_sections = "\n".join(relevant_sections)
                return f"QUANTUM GUIDELINES (Showing sections matching '{query}'):\n\n{joined_sections}"
                
        except Exception as e:
            return f"Error reading guidelines: {str(e)}"
