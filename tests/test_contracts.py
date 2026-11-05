import pytest
from pydantic import ValidationError

from hlagent.agents import safe_text
from hlagent.models import PlanStep


def test_path_redaction_retains_research_request():
    result = safe_text(r'C:\Users\Researcher\data.bed 로 HLA 연관분석해줘')
    assert "Researcher" not in result
    assert "HLA 연관분석해줘" in result
    result = safe_text(r'Use "C:\Users\Researcher\my study\data.bed" for HLA association')
    assert "Researcher" not in result and "HLA association" in result


def test_retrieved_paths_cannot_escape_job_directory():
    with pytest.raises(ValidationError):
        PlanStep(id="../../outside", tool="prepare")


def test_genotype_tables_do_not_enter_model_prompt():
    with pytest.raises(ValueError, match="Genotype/sample"):
        safe_text("0/0 0/1 1/1 0/0 0/1 1/1 ")
