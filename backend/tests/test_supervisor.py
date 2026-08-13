import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.asyncio
async def test_create_sub_agent_returns_final_ai_message():
    from src.agents.supervisor import create_sub_agent

    fake_graph = MagicMock()
    fake_graph.ainvoke.return_value = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="final answer")]
    }
    fake_llm = MagicMock()
    fake_tools = [MagicMock(), MagicMock()]

    with patch("src.agents.supervisor.create_react_agent", return_value=fake_graph) as mock_cra:
        agent_tool = create_sub_agent(
            name="research_agent",
            description="Research things",
            tools=fake_tools,
            llm=fake_llm,
        )

    assert agent_tool.name == "research_agent"
    assert agent_tool.description == "Research things"
    result = await agent_tool.ainvoke({"query": "tim kiem"})
    assert result == "final answer"
    mock_cra.assert_called_once_with(model=fake_llm, tools=fake_tools)
    called_input = fake_graph.ainvoke.call_args.args[0]
    assert isinstance(called_input["messages"][0], HumanMessage)
    assert called_input["messages"][0].content == "tim kiem"


@pytest.mark.asyncio
async def test_create_sub_agent_skips_tool_message_when_ended_on_tool():
    from src.agents.supervisor import create_sub_agent

    fake_graph = MagicMock()
    fake_graph.ainvoke.return_value = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
            AIMessage(content="real answer"),
        ]
    }

    with patch("src.agents.supervisor.create_react_agent", return_value=fake_graph):
        agent_tool = create_sub_agent(
            name="info_agent",
            description="Info things",
            tools=[MagicMock()],
            llm=MagicMock(),
        )

    result = await agent_tool.ainvoke({"query": "gio"})
    assert result == "real answer"
