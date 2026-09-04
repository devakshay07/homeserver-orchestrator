class PromptBuilder:
    @staticmethod
    def build_generation_prompt(spec: str) -> str:
        return f"""
        Please generate a complete, production-ready project based on the following specification.
        Do not produce prototypes or leave TODO placeholders. 
        Generate all source files, configurations, documentation, and tests.

        # Specification:
        <spec>
        {spec}
        </spec>
        """
        
    @staticmethod
    def build_readme_update_prompt(improvements: str) -> str:
        return f"""
        Please update the README.md based on the following review feedback.
        
        # Feedback:
        <feedback>
        {improvements}
        </feedback>
        """
