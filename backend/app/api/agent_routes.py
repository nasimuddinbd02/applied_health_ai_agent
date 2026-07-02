"""Appointment-agent controller: conversational booking chat + history."""

from fastapi import APIRouter

from app.models.schemas import AgentRequest, AgentResponse
from app.providers.appointment_provider import AppointmentProvider
from app.providers.gateway_provider import GatewayProvider


class AgentController:
    def __init__(self, gateway: GatewayProvider, appointments: AppointmentProvider) -> None:
        self._gateway = gateway
        self._appt = appointments
        self.router = APIRouter(prefix="/api/agent", tags=["agent"])
        self._register()

    def _register(self) -> None:
        r = self.router
        r.add_api_route("/appointment", self.chat, methods=["POST"], response_model=AgentResponse)
        r.add_api_route("/appointment/{thread_id}/history", self.history, methods=["GET"])

    async def chat(self, req: AgentRequest):
        result = await self._gateway.run_agent(
            "appointment", req.message, thread_id=req.thread_id, patient_id=req.patient_id
        )
        return AgentResponse(
            thread_id=result.thread_id,
            final_text=result.final_text,
            transcript=result.transcript,
            tool_calls=result.tool_calls,
        )

    def history(self, thread_id: str):
        return self._appt.chat_history(thread_id)
