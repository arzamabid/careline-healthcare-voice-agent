import asyncio

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    ChatMessage,
    JobContext,
    StopResponse,
    cli,
)

from agent.graph import build_graph
from agent.voice.livekit_stt import FasterWhisperSTT
from agent.voice.livekit_tts import KokoroTTS
from agent.voice.vad import get_vad
from db.models import CallSession
from db.session import get_db_session
from observability.session_persistence import (
    persist_call_session,
)

load_dotenv()

server = AgentServer()


class CarelineAgent(Agent):
    def __init__(
        self,
        thread_id: str,
        db_session_id: int,
    ) -> None:
        super().__init__(
            instructions=(
                "Careline local healthcare "
                "administrative assistant."
            )
        )

        self.graph = build_graph()

        # LangGraph thread ID
        self.thread_id = thread_id

        # Real PostgreSQL CallSession.id
        self.db_session_id = db_session_id

        # True after the first caller turn initializes
        # the LangGraph state.
        self.initialized = False

        # Once True, ignore all additional speech.
        self.call_ended = False

        # Prevent overlapping speech / microphone races.
        self._speaking_lock = asyncio.Lock()

        # Number of consecutive LiveKit inactivity events.
        self.silence_events = 0

        # Evaluation / observability flags.
        self.reengagement_attempted = False
        self.interruption_enabled = False

    async def speak_without_listening(
            self,
            text: str,
            *,
            final: bool = False,
            interruptible: bool = False,
    ) -> None:
        """
        Speak Careline TTS.

        Normal responses disable microphone input to prevent
        local speaker echo from reaching STT.

        Selected responses may be interruptible. For those
        responses the microphone remains enabled and LiveKit
        is allowed to stop playback when caller speech is
        detected.

        If final=True, microphone input remains disabled.
        """

        if not isinstance(text, str):
            return

        if not text.strip():
            return

        async with self._speaking_lock:
            print(
                "AGENT SPEAKING:",
                repr(text),
            )

            # =============================================
            # Interruptible speech
            # =============================================

            if interruptible and not final:
                print(
                    "INTERRUPTIBLE SPEECH ENABLED"
                )

                self.session.input.set_audio_enabled(
                    True
                )

                speech_handle = self.session.say(
                    text,
                    add_to_chat_ctx=True,
                    allow_interruptions=True,
                )

                await speech_handle.wait_for_playout()

                print(
                    "INTERRUPTIBLE PLAYOUT FINISHED"
                )

                return

            # =============================================
            # Echo-protected speech
            # =============================================

            self.session.input.set_audio_enabled(
                False
            )

            print(
                "MICROPHONE DISABLED"
            )

            try:
                speech_handle = self.session.say(
                    text,
                    add_to_chat_ctx=True,
                    allow_interruptions=False,
                )

                await speech_handle.wait_for_playout()

                print(
                    "AGENT PLAYOUT FINISHED"
                )

                if not final:
                    await asyncio.sleep(
                        0.5
                    )

            finally:
                if (
                        not final
                        and not self.call_ended
                ):
                    self.session.input.set_audio_enabled(
                        True
                    )

                    print(
                        "MICROPHONE ENABLED"
                    )

    async def handle_user_away(
            self,
    ) -> bool:
        """
        Handle one LiveKit user-away event.

        First inactivity:
            briefly re-engage the caller.

        Second consecutive inactivity:
            close the call safely.

        Returns True when the call should be closed.
        """

        if self.call_ended:
            return True

        self.silence_events += 1

        print(
            "CALLER SILENCE EVENT:",
            self.silence_events,
        )

        if self.silence_events == 1:
            self.reengagement_attempted = True

            await self.speak_without_listening(
                "Are you still there? "
                "I'm here if you'd like to continue."
            )

            return False

        response = (
            "I haven't heard a response, so I'll end "
            "the call for now. "
            "You can call Careline again whenever "
            "you need assistance. Goodbye."
        )

        self.call_ended = True

        await self.speak_without_listening(
            response,
            final=True,
        )

        return True

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        """
        Handle one completed caller utterance.

        Caller
            ↓
        faster-whisper
            ↓
        LangGraph
            ↓
        response_text
            ↓
        Kokoro / LiveKit
        """

        # =================================================
        # 1. Ignore input after call completion
        # =================================================

        if self.call_ended:
            print(
                "IGNORING USER INPUT: "
                "call has already ended"
            )

            raise StopResponse()

        # =================================================
        # 2. Get STT transcript
        # =================================================

        caller_text = (
            new_message.text_content.strip()
        )

        print(
            "VOICE TRANSCRIPT:",
            repr(caller_text),
        )

        if not caller_text:
            raise StopResponse()

        # Caller is active again.
        self.silence_events = 0

        # =================================================
        # 3. LangGraph thread configuration
        # =================================================

        config = {
            "configurable": {
                "thread_id":
                    self.thread_id,
            }
        }

        # =================================================
        # 4. First caller turn
        # =================================================

        if not self.initialized:
            graph_input = {
                # -----------------------------------------
                # Session IDs
                # -----------------------------------------

                # LangGraph / LiveKit session identifier
                "session_id":
                    self.thread_id,

                # PostgreSQL call_sessions.id
                "db_session_id":
                    self.db_session_id,

                "original_request_text":
                    None,

                # -----------------------------------------
                # Current caller text
                # -----------------------------------------

                "caller_text":
                    caller_text,

                "conversation":
                    [],

                # Greeting already spoken by LiveKit.
                "greeted":
                    True,

                # -----------------------------------------
                # Identity
                # -----------------------------------------

                "verified_patient_id":
                    None,

                "verification_attempts":
                    0,

                "verification_fields":
                    {},

                "identity_status":
                    None,

                # -----------------------------------------
                # Intent / workflow
                # -----------------------------------------

                "intent":
                    None,

                "active_workflow":
                    None,

                "collected_fields":
                    {},

                # -----------------------------------------
                # Tool results
                # -----------------------------------------

                "tool_results":
                    [],

                # -----------------------------------------
                # Safety
                # -----------------------------------------

                "safety_flags":
                    [],

                "escalation_required":
                    False,

                # -----------------------------------------
                # Appointment
                # -----------------------------------------

                "appointment_action":
                    None,

                "appointment_specialty":
                    None,

                "appointment_date":
                    None,

                "selected_appointment_id":
                    None,

                # Clinic currently being discussed.
                "last_referenced_clinic":
                    None,

                # -----------------------------------------
                # Confirmation
                # -----------------------------------------

                "pending_confirmation":
                    None,

                "confirmation_required":
                    False,

                "confirmation_received":
                    False,

                "confirmation_token":
                    None,

                # -----------------------------------------
                # Pre-visit intake
                # -----------------------------------------

                "intake_index":
                    0,

                "intake_answers":
                    {},

                "intake_review_required":
                    False,

                "intake_confirmed":
                    False,

                # -----------------------------------------
                # Closing
                # -----------------------------------------

                "awaiting_more_help":
                    False,

                "call_ended":
                    False,

                # -----------------------------------------
                # Summary / metrics
                # -----------------------------------------

                "call_summary":
                    None,

                "metrics":
                    {},
            }

            self.initialized = True

        # =================================================
        # 5. Following caller turns
        # =================================================

        else:
            # LangGraph checkpointer already has the
            # previous state, including db_session_id.
            graph_input = {
                "caller_text":
                    caller_text,
            }

        # =================================================
        # 6. Run LangGraph
        # =================================================

        try:
            result = await asyncio.to_thread(
                self.graph.invoke,
                graph_input,
                config,
            )

        except Exception as exc:  # noqa: BLE001
            print(
                "LANGGRAPH ERROR:",
                repr(exc),
            )

            await self.speak_without_listening(
                
                    "I'm sorry, I encountered a problem "
                    "processing that request. "
                    "Please try again."
                
            )

            raise StopResponse()

        # =================================================
        # 7. Get response text
        # =================================================

        response = result.get(
            "response_text"
        )

        # Never allow a completely silent graph turn.
        if (
            not isinstance(
                response,
                str,
            )
            or not response.strip()
        ):
            response = (
                "I'm sorry, I didn't quite understand that. "
                "Could you please say that again?"
            )

        persist_call_session(
            result,
            finalize=False,
        )

        # =================================================
        # Debug information
        # =================================================

        print(
            "GRAPH NODE:",
            result.get(
                "current_node"
            ),
        )

        print(
            "GRAPH RESPONSE:",
            repr(response),
        )

        print(
            "ACTIVE WORKFLOW:",
            result.get(
                "active_workflow"
            ),
        )

        print(
            "INTENT:",
            result.get(
                "intent"
            ),
        )

        print(
            "DB SESSION ID:",
            result.get(
                "db_session_id"
            ),
        )

        print(
            "AWAITING MORE HELP:",
            result.get(
                "awaiting_more_help"
            ),
        )

        print(
            "CALL ENDED STATE:",
            result.get(
                "call_ended"
            ),
        )

        # =================================================
        # 8. Final response / goodbye
        # =================================================

        if result.get(
            "call_ended",
            False,
        ):
            persist_call_session(
                result,
                finalize=True,
            )

            print(
                "FINAL GOODBYE:",
                repr(response),
            )

            # Speak complete final response while microphone
            # remains disabled.
            await self.speak_without_listening(
                response,
                final=True,
            )

            # Mark local agent ended only after audio playback.
            self.call_ended = True

            print(
                "CALL ENDED"
            )

            raise StopResponse()

        # =================================================
        # 9. Normal assistant response
        # =================================================

        appointment_options = (
                result.get(
                    "appointment_options"
                )
                or []
        )

        interruptible = (
                result.get("active_workflow")
                == "appointment"
                and len(appointment_options) > 0
        )

        if interruptible:
            self.interruption_enabled = True

        await self.speak_without_listening(
            response,
            interruptible=interruptible,
        )

        raise StopResponse()


@server.rtc_session(
    agent_name="careline-agent"
)
async def careline_session(
    ctx: JobContext,
) -> None:
    """
    Start one Careline voice session.
    """

    # =====================================================
    # 1. Create LangGraph / LiveKit thread identifier
    # =====================================================

    thread_id = (
        f"voice-{ctx.room.name}"
    )

    print(
        "STARTING CARELINE SESSION:",
        thread_id,
    )

    # =====================================================
    # 2. Create PostgreSQL CallSession
    # =====================================================

    with get_db_session() as db:
        call_session = CallSession(
            patient_id=None,
            intent=None,
            outcome=None,
            escalated=False,
            summary_json=None,
            verified=False,
            verified_patient_id=None,
        )

        db.add(
            call_session
        )

        db.commit()

        db.refresh(
            call_session
        )

        db_session_id = (
            call_session.id
        )

    print(
        "DATABASE CALL SESSION CREATED:",
        db_session_id,
    )

    # =====================================================
    # 3. Local voice pipeline
    # =====================================================

    session = AgentSession(
        stt=FasterWhisperSTT(),
        tts=KokoroTTS(),
        vad=get_vad(),
        user_away_timeout=15.0,
    )

    # Pass BOTH identifiers to the agent.
    agent = CarelineAgent(
        thread_id=thread_id,
        db_session_id=db_session_id,
    )

    inactivity_task: asyncio.Task | None = None

    async def handle_inactivity() -> None:
        should_close = (
            await agent.handle_user_away()
        )

        if should_close:
            session.shutdown()

    @session.on("user_state_changed")
    def on_user_state_changed(
            event,
    ) -> None:
        nonlocal inactivity_task

        print(
            "VOICE USER STATE:",
            event.new_state,
        )

        if event.new_state == "away":
            if (
                    inactivity_task is None
                    or inactivity_task.done()
            ):
                inactivity_task = asyncio.create_task(
                    handle_inactivity()
                )

            return

        # Caller returned.
        if (
                inactivity_task is not None
                and not inactivity_task.done()
        ):
            inactivity_task.cancel()

        inactivity_task = None

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    # =====================================================
    # 4. Initial greeting
    # =====================================================

    greeting = (
        "Hello, you've reached Careline. "
        "I'm an AI patient-services assistant "
        "using synthetic demo data. "
        "How can I help you today?"
    )

    # Same microphone-safe mechanism used for every
    # other assistant response.
    await agent.speak_without_listening(
        greeting
    )

    print(
        "CARELINE READY FOR CALLER"
    )


if __name__ == "__main__":
    cli.run_app(
        server
    )