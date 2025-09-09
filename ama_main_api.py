from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, List
from dotty_dictionary import dotty

from langchain_core.messages import HumanMessage, SystemMessage
from core.logger import logger
from core.config import Config
from core.session.base import Session
from core.session.backends.redis import RedisBackend
from core.utilities import convert_to_langchain_messages
from fastapi.middleware.cors import CORSMiddleware

from orchestration.workflow import create_primary_graph
from orchestration.state import default_state
from orchestration.schema import Node

app = FastAPI(root_path="/proxy/8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific origins if you want to restrict access
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

class UserInput(BaseModel):
    q: str

class Main:
    def __init__(self, session_id: str, smb_id: str) -> None:
        self.session_id = session_id
        self.smb_id = smb_id
        self.device = None
        self.AppConfig, self.config, self.context = self._initialize_config()
        self.session = self._initialize_session(self.session_id, self.smb_id, self.device)
        self.app_context = self._initialize_app_context(self.AppConfig, self.session, self.session_id, self.smb_id)
        self.messages = self._initialize_messages(self.session)

        self.initial_state = default_state()
        self.initial_state["device"] = self.device

    @staticmethod
    def _initialize_config():
        AppConfig = Config()
        config = AppConfig.get_data()
        context = AppConfig.get_context()
        return AppConfig, config, context

    @staticmethod
    def _initialize_session(session_id: str, smb_id: str, device: str) -> Session:
        backend = RedisBackend()
        session = Session(backend)
        session.set_session_id(session_id)

        try:
            session_data = session.get_data("session") or {}

            session_data["session_id"] = session_id
            if smb_id is not None:
                session_data["smb_id"] = smb_id
            if device is not None:
                session_data["device"] = device

            session.set_data("session", session_data)
            return session

        except Exception as e:
            logger.error(f"Failed to get or set session: {e}")
            return session

    @staticmethod
    def _initialize_app_context(AppConfig: Config, session: Session, session_id: str, smb_id: str) -> Dict[str, Any]:
        app_context = AppConfig.load_app_context(visitor_session=session_id, smb_id=smb_id)

        try:
            stored_context = session.get_data("app_context")
            if stored_context is None:
                stored_context = app_context.to_dict()
                session.set_data("app_context", stored_context)
            return dotty(stored_context)
        except Exception as e:
            logger.error(f"Failed to get or set app_context in session: {e}")
            return app_context

    @staticmethod
    def _initialize_messages(session: Session) -> List[Dict[str, Any]]:
        try:
            return session.get_data("messages") or []
        except Exception as e:
            logger.error(f"Failed to get messages from session: {e}")
            return []

    async def processing_request(self, user_input):
        agent_config = {
            "configurable": {
                "thread_id": "t-" + self.session_id,
            },
            "recursion_limit": 150
        }

        agent = create_primary_graph(session=self.session)

        messages = []
        ext_messages = []
        if len(self.messages) > 0:
            ext_messages = convert_to_langchain_messages(self.messages)
        else:
            ext_messages = [HumanMessage(content=user_input)]

        input_state = self.initial_state
        input_state["messages"] = ext_messages

        content = ""
        debug_info = []
        async for s in agent.astream(input_state, config=agent_config, stream_mode="updates", debug=True):
            debug_info.append(s)
            the_keys = list(s.keys())

            if Node.GENERATOR.value in the_keys or Node.AUTHORIZATION.value in the_keys or Node.VOIP.value in the_keys or Node.INITIATOR.value in the_keys or Node.ROUTER.value in the_keys or Node.FOLLOW_UP.value in the_keys:
                actor = 'ai'
                the_response = list(s.values())[0]
                messages = the_response.get("messages", [])

                data = the_response.get("data", [])

                if len(messages) > 0 or len(data) > 0:

                    if len(messages) > 0:
                        the_message = messages[-1]
                        content = the_message.content

                    if actor == "action":
                        actor = 'system'

                    response = {
                        "role": actor,
                        "content": content,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    if 'data' in the_response and len(the_response["data"]) > 0:
                        response["data"] = the_response["data"]

                    if 'followup_message' in the_response and the_response["followup_message"].strip():
                        response["followup_message"] = the_response["followup_message"]

                    self.session.push("messages", response)

        return content, debug_info

    async def run(self, user_input: str):
        if user_input:
            message = {
                "content": user_input,
                "role": "user",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            self.session.push("messages", message)

            response_content, debug_info = await self.processing_request(user_input)
            return response_content, debug_info
        return None, None

    @staticmethod
    def _cleanup_session(session: Session):
        try:
            session.set_data("last_access", datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Failed to update session on exit: {str(e)}")



async def verify_headers(
    x_session_key: str = Header(None, alias="x-session-key"),
    x_smb_key: str = Header(None, alias="x-smb-key")
):
    if not x_session_key or not x_smb_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing required headers")
    return {"x_session_key": x_session_key, "x_smb_key": x_smb_key}

@app.post("/chat-completion")
async def chat(
    user_input: UserInput,
    headers: dict = Depends(verify_headers)
):
    visitor_session = headers["x_session_key"]
    smb_id_from_header = headers["x_smb_key"]
    main = Main(session_id=visitor_session, smb_id=smb_id_from_header)
    main.session.set_data("smb_id", smb_id_from_header)

    try:
        response, debug_info = await main.run(user_input.q)

        if not response:
            return {"error": "Failed to process the request.", "data": None}
        return {"data": response, "error": None, "debug_info": debug_info}
    except Exception as e:
        logger.exception(f"Error in chat completion: {str(e)}")
        return {"error": str(e), "data": None}

@app.get("/")
async def read_root():
    return {"data": "Welcome to the Assistant API"}
