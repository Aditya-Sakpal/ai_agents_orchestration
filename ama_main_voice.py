import os
import asyncio
import json
import traceback
from typing import Dict, Any

from livekit import agents
from livekit.agents import (
    AgentSession, 
    Agent, 
    RoomInputOptions, 
    ConversationItemAddedEvent,

)

from livekit.plugins import (
    noise_cancellation,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from core.greetings import GreetingPipeline
from core.logger import logger
from core.session.base import Session
from core.session.backends.redis import RedisBackend
from core.handlers.utility_api import UtilityAPI
from core.utilities import format_message, format_conversation_item

from orchestration.workflow import create_primary_graph

from voice.chains import BasicChain
from voice.setup import initialize_tts, default_initialization

from dotenv import load_dotenv
load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")


def _initialize_session(session_id: str, smb_id: str, device: str) -> Session:
    session = Session(RedisBackend())
    session.set_session_id(session_id)
    
    try:
        session_data = {
            "session_id": session_id,
            "smb_id": smb_id,
            "device": device
        }
    
        session.set_data("session", session_data)
        return session
    
    except Exception as e:
        logger.error(f"Failed to get or set session: {e}")
        return session      

async def publish_data_with_retry(ctx, participant, topic: str, payload: Dict[str, Any], retry_count: int = 0, max_retries: int = 3, retry_delay: float = 1.0):
    try:
        
        await ctx.room.local_participant.publish_data(
            payload,
            reliable=True,
            destination_identities=[participant.identity],
            topic=topic
        )
    except Exception as e:
        if retry_count < max_retries:
            logger.warning(f"Failed to publish data, retrying... (attempt {retry_count + 1})")
            await asyncio.sleep(retry_delay)
            await publish_data_with_retry(ctx, participant, topic, payload, retry_count + 1, max_retries, retry_delay)
        else:
            logger.error(f"Failed to publish data after {max_retries} attempts: {e}")

async def send_data_to_participant(ctx, participant, data: Dict[str, Any]):
    logger.info(f"[PARTICIPANT] Attempting to send data to participant: {data}")

    try:
        if isinstance(data, list):
            for item in data:
                topic = item["topic"]
                payload = json.dumps(item["payload"])
                logger.info(f"[PARTICIPANT] Sending list item - Topic: {topic}, Payload: {payload}")
                await publish_data_with_retry(ctx, participant, topic, payload)

        elif "topic" in data and "payload" in data:
            topic = data["topic"]
            payload = json.dumps(data["payload"])
            logger.info(f"[PARTICIPANT] Sending single item - Topic: {topic}, Payload: {payload}")
            await publish_data_with_retry(ctx, participant, topic, payload)

    except Exception as e:
        logger.error(f"[PARTICIPANT] Error in send_data_to_participant: {e}")
        logger.error(traceback.format_exc())

async def entrypoint(ctx: agents.JobContext):

    logger.debug("Starting entrypoint...")

    # user input transcribed.
    await ctx.connect()


    # define required variables.
    the_device = 'ew'
    the_session_id = None
    the_session = None
    session = None  # Initialize session variable

    # wait for participant.
    participant = await ctx.wait_for_participant()
    participant_attributes = participant.attributes
    
    logger.info(f"participant_attributes: {participant_attributes}")

    # if local, use the session id and smb id from the environment variables.
    if os.getenv('APP_ENV') == 'local':
        participant_attributes = {
            "session_id": os.getenv('USER_SESSION_ID'),
            "smb_id": os.getenv('SMB_ID'),
        }


    logger.info(f"participant_attributes: {participant_attributes}")

    # if participant attributes are not empty, use the session id and smb id from the participant attributes.
    if participant_attributes:
        if "session_id" in participant_attributes and "smb_id" in participant_attributes:
            session_id = participant_attributes.get("session_id")
            smb_id = participant_attributes.get("smb_id")
            
            the_session_id = session_id
            the_session = _initialize_session(session_id, smb_id, the_device)
                    
        if "sip.phoneNumber" in participant_attributes and "sip.trunkPhoneNumber" in participant_attributes:
            participantNo = participant.attributes.get("sip.phoneNumber", None)
            smbNo = participant.attributes.get("sip.trunkPhoneNumber", None)
            
            client = UtilityAPI()
            result = client.create_contact_session(
                visitor_contact=participantNo,
                smb_contact=smbNo
            )

            if result and result["success"]:
                data = result["data"]
                the_session_id = data["session_id"]
                the_device = os.getenv('DEVICE_VOIP')
                the_session = _initialize_session(the_session_id, data["smb_id"], the_device)
            else:
                logger.error("Failed to create contact session.")
    
    if the_session:

        logger.debug("Creating AgentSession...")

        openai_api_key = os.getenv("OPENAI_API_KEY")
        initial_state = ctx.proc.userdata["initial_state"]
        initial_state["device"] = the_device      
        
        session = AgentSession(
            stt=ctx.proc.userdata["stt"],
            tts=ctx.proc.userdata["tts"],
            vad=ctx.proc.userdata["vad"],
            turn_detection=MultilingualModel(),
        )
        logger.debug("AgentSession created...")

        # conversation item added. [+]
        @session.on("conversation_item_added")
        def _conversation_item_added(ev: ConversationItemAddedEvent):

            # push message to session
            the_message = format_conversation_item(ev.item)

            # Handling data and followup message.
            the_llm = session._agent.llm

            if the_llm:

                # send data to participant.
                data = the_llm.get_data()
                if len(data) > 0:
                    asyncio.create_task(send_data_to_participant(ctx, participant, data))

                # clear data.
                session._agent.llm.set_data([])

                # send followup message to participant.
                followup_message = the_llm.get_followup_message()
                if followup_message:
                    the_message["followup_message"] = followup_message
                    payload = {
                        "topic": "followup_message",
                        "payload": {
                            "content": followup_message
                        }
                    }
                    asyncio.create_task(send_data_to_participant(ctx, participant, payload))
                    
                    # clear followup message.
                    session._agent.llm.set_followup_message("")

            # Push messages to session with error handling
            try:
                the_session.push("messages", the_message)
            except Exception as e:
                logger.error(f"[AGENT] Failed to push message to session: {e}")

        # create the graph.
        graph = create_primary_graph(
            session=the_session
        )

        # create the chain.
        chain = BasicChain(
            session_id=the_session_id,
            openai_key=openai_api_key,
            initial_state=initial_state,
            agent=graph
        )

        # create the agent.
        agent = Agent(
            instructions="",
            llm=chain,
        )

        # start the session
        logger.debug("Starting session...")
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
                close_on_disconnect=False,
            ),
        )            

        # Initial reply to user.
        history = session.history.to_dict()
        if "items" in history and len(history["items"]) == 0:
            # greeting = f"Greet to user (include name if there) and introduce yourself!"
            greeting = await GreetingPipeline.greeting(session_id=the_session_id)

            message = greeting["messages"]
            await session.say(message, allow_interruptions=False)
    else:
        logger.error("No session was created. Cannot proceed with voice assistant.")
        return


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=default_initialization,
        )
    )