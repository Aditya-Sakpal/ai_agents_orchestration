import os
import asyncio
import traceback

import streamlit as st
from langchain_core.messages import HumanMessage 
from datetime import datetime
from dotenv import load_dotenv

from typing import Dict, Any, List

from core.logger import logger
from core.config import Config
from core.greetings import GreetingPipeline
from core.utilities import convert_to_langchain_messages
from core.session.backends.redis import RedisBackend
from core.session.base import Session
from core.ux.components import (
    MessageResponse, local_css, display_message, display_history, display_input,
    SelectorConfig, create_selector, display_entity_details, format_entity_name,
    create_message_container, clear_messages, add_message
)
from core.handlers.db import get_active_smbs, get_visitors

from orchestration.state import default_state
from orchestration.workflow import create_primary_graph
from orchestration.schema import Node


# Load environment variables
load_dotenv(
    override=True
)

class Main():

    def __init__(self):
        self._enabled_langsmith()
        
        if os.getenv('APP_ENV') == 'local':
            self.session_id = os.getenv('USER_SESSION_ID')
            self.smb_id = os.getenv('SMB_ID')
            self.device = os.getenv('DEVICE_EW')
        else:
            self.session_id = None
            self.smb_id = None
            self.device = None
        
        self.AppConfig = Config()
        self.config = self.AppConfig.get_data()
        self.session = self._initialize_session(self.session_id, self.smb_id, self.device)
        
        self.initial_state = default_state()
        self.initial_state["device"] = self.device
        
        self.messages = self._initialize_messages(self.session)
        self.messages_container = None

    @staticmethod
    def _enabled_langsmith():
        os.environ["LANGCHAIN_TRACING_V2"] = os.getenv('LANGCHAIN_TRACING_V2', "true")
        os.environ["LANGCHAIN_API_KEY"] = os.getenv('LANGCHAIN_API_KEY')
        os.environ["LANGCHAIN_PROJECT"] = os.getenv('LANGCHAIN_PROJECT')
    
    @staticmethod
    def _initialize_session(session_id: str, smb_id: str, device: str) -> Session:
        backend = RedisBackend()
        session = Session(backend)
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
    
    @staticmethod
    def _initialize_messages(session: Session) -> List[Dict[str, Any]]:
        try:
            messages = session.get_data("messages") or []
            if len(messages) > 10:
                messages = messages[-10:]
            return messages
        except Exception as e:
            logger.error(f"Failed to get messages from session: {e}")
            return []
        
    async def processing_request(self, user_input):
        try:
            # Validate input
            if not user_input or not user_input.strip():
                logger.warning("Empty user input received")
                return
            
            agent_config = {
                "configurable": {
                    "thread_id": "t-" + self.session_id,
                },
                "recursion_limit": 50,  # Reduced from 150 to prevent memory issues
                "recursion_count": 0    # Initialize recursion counter
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
            
            # Add timeout to prevent hanging
            import asyncio
            try:
                async with asyncio.timeout(120000.0):  # 2 minute timeout
                    async for s in agent.astream(input_state, config=agent_config, stream_mode="updates", debug=True):
                        the_keys = list(s.keys())
                        
                        if Node.GENERATOR.value in the_keys or Node.AUTHORIZATION.value in the_keys or Node.VOIP.value in the_keys or Node.INITIATOR.value in the_keys or Node.ROUTER.value in the_keys or Node.FOLLOW_UP.value in the_keys:
                            actor = 'ai'
                            the_response = list(s.values())[0]
                            messages = the_response.get("messages", [])
                            
                            data = the_response.get("data", [])

                            if len(messages) > 0 or len(data) > 0:
                                
                                content = ''

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
                                
                                if 'generator_state' in the_response:
                                    if 'followup_message' in the_response['generator_state'] and the_response["generator_state"]["followup_message"].strip():
                                        response["followup_message"] = the_response["generator_state"]["followup_message"]
                                    
                                self.session.push("messages", response)
                                display_message(MessageResponse(response), container=self.messages_container)
                                
            except asyncio.TimeoutError:
                logger.error("Processing request timed out")
                error_response = {
                    "role": "system",
                    "content": "I apologize, but the request is taking too long to process. Please try again with a simpler request.",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.session.push("messages", error_response)
                display_message(MessageResponse(error_response), container=self.messages_container)
                
        except Exception as e:
            logger.error(f"Error in processing_request: {e}")
            logger.error(traceback.format_exc())
            
            error_response = {
                "role": "system",
                "content": "I apologize, but an error occurred while processing your request. Please try again.",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.session.push("messages", error_response)
            display_message(MessageResponse(error_response), container=self.messages_container)
        
    async def run(self):
        messages = self.session.get_data("messages", [])

        if 'current_session_id' in st.session_state:
            self.session_id = st.session_state.current_session_id
            self.session = self._initialize_session(self.session_id, self.smb_id, self.device)

        local_css(self.config.get("app")["theme"])
        self.messages_container = create_message_container()

        with st.sidebar:
            st.title("Settings")
            try:
                active_smbs = get_active_smbs(preferences=True)
                #logger.info(f"Retrieved active SMBs in Streamlit: {active_smbs}")
                
                if not isinstance(active_smbs, dict):
                    st.error("Invalid data format received. Please contact support.")
                    logger.error(f"Expected dict but got {type(active_smbs)}: {active_smbs}")
                    return
                
                if len(active_smbs) == 0:
                    st.warning("No active businesses found.")
                    logger.warning("Empty SMB dictionary received")
                    return
                
                smb_options = {}
                for smb_id, smb in active_smbs.items():
                    if smb and isinstance(smb, dict):
                        display_name = format_entity_name(
                            smb,
                            id_field='id',
                            fields=['name', 'website']
                        )
                        smb_options[display_name] = smb_id
                        #logger.info(f"Added SMB option: {display_name} -> {smb_id}")

                smb_config = SelectorConfig(
                    title="Select Business",
                    key="smb_selector",
                    default_option="No Business Selected",
                    show_details=True
                )
                
                selected_smb_id = create_selector(
                    options=smb_options,
                    config=smb_config,
                    container=st.sidebar,
                    details_formatter=lambda smb, container: display_entity_details(
                        active_smbs.get(smb, {}),
                        container=container
                    )
                )
                
                if selected_smb_id:
                    self.smb_id = selected_smb_id
                    logger.info(f"Selected SMB ID: {self.smb_id}")
                    
                    try:
                        visitors_data = get_visitors(
                            smb_id=int(self.smb_id),
                            sort_by='created_at',
                            sort_order='desc'
                        )
                        #logger.info(f"Retrieved visitors for SMB {self.smb_id}: {visitors_data}")
                        
                        if visitors_data['total_count'] > 0:
                            visitor_options = {}
                            visitor_details = {}
                            for visitor in visitors_data['visitors']:
                                display_name = format_entity_name(
                                    visitor,
                                    id_field='id',
                                    fields=['name', 'email', 'phone']
                                )
                                visitor_options[display_name] = visitor['session_id']
                                visitor_details[visitor['session_id']] = visitor
                                #logger.info(f"Added visitor option: {display_name} -> {visitor['session_id']}")
                            
                            visitor_config = SelectorConfig(
                                title="Select Visitor",
                                key="visitor_selector",
                                default_option="No Visitor Selected",
                                show_details=True
                            )
                            
                            selected_session_id = create_selector(
                                options=visitor_options,
                                config=visitor_config,
                                container=st.sidebar,
                                details_formatter=lambda session_id, container: display_entity_details(
                                    visitor_details.get(session_id, {}),
                                    container=container
                                )
                            )
                            
                            if selected_session_id:
                                self.session_id = selected_session_id
                                st.session_state.current_session_id = self.session_id
                                
                                self.session.set_session_id(self.session_id)
                                
                                self.session = self._initialize_session(self.session_id, self.smb_id, self.device)
                                
                                self.messages = self._initialize_messages(self.session)
                                
                                clear_messages(self.messages_container)
                                
                                self.session.set_data("messages", self.messages)
                                
                                if len(self.messages) > 0:
                                    if st.session_state.get("messages_displayes", False):
                                        for msg in self.messages:
                                            display_message(MessageResponse(msg), container=self.messages_container)
                                        st.session_state["messages_displayed"] = True
                                        # breakpoint()
                                else:
                                    content = await GreetingPipeline.greeting(session_id=self.session_id)

                                    welcome_msg = add_message(
                                        messages=self.messages,
                                        content=content["messages"],
                                        role="assistant"
                                    )
                                    
                                    st.session_state["messages_displayed"] = True
                                    self.session.set_data("messages", self.messages)
                                    

                                logger.info(f"Selected visitor session ID: {self.session_id}")
                                logger.info(f"Loaded {len(self.messages)} messages for visitor")
                            else:
                                self.session_id = None
                                if 'current_session_id' in st.session_state:
                                    del st.session_state.current_session_id
                                
                                self.messages = []
                                self.session.set_data("messages", [])
                                clear_messages(self.messages_container)
                                
                                st.sidebar.info("No visitor selected")
                    except Exception as e:
                        logger.error(f"Error loading visitor selector: {e}")
                        logger.error(traceback.format_exc())
                        st.error("Unable to load visitor list. Please try again later.")
            except Exception as e:
                logger.error(f"Error loading SMB selector: {e}")
                logger.error(traceback.format_exc())
                st.error("Unable to load business list. Please try again later.")

        user_input = display_input(
            on_change_func = display_history(
                messages_container=self.messages_container, 
                messages=self.messages
            ),
        )
        
        if user_input:
            input_msg = add_message(
                messages=self.messages,
                content=user_input,
                role="user"
            )
            
            self.session.set_data("messages", self.messages)
            display_message(MessageResponse(input_msg), container=self.messages_container)
            
            try:
                logger.info("\n\n\n ------------------------------------------------------------------------------Processing request...------------------------------------------------------------------------------ \n\n\n")
                await self.processing_request(user_input)

            except Exception as e:
                logger.exception(e)
                error_msg = add_message(
                    messages=self.messages,
                    content="We're experiencing some issues right now and are working hard to resolve them. Please try again later. Thank you for your patience.",
                    role="system"
                )
                self.session.set_data("messages", self.messages)
                display_message(MessageResponse(error_msg), container=self.messages_container)


        # if not user_input and len(messages) == 0:
            
        #     content = await GreetingPipeline.greeting(session_id=self.session_id)

        #     greetings = {
        #         "role": "assistant",
        #         "content": content["messages"],
        #         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #     }

        #     self.session.push("messages", greetings)

        #     display_message(
        #         MessageResponse(greetings),
        #         container=self.messages_container
        #     )
        #     self.session.set_data("messages", self.messages)
        #     #display_message(MessageResponse(welcome_msg), container=self.messages_container)

        logger.info("\n\n\n ------------------------------------------------------------------------------Finished Processing request...------------------------------------------------------------------------------ \n\n\n")


# run the application
if __name__ == "__main__":
    try:
        asyncio.run(Main().run())
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.error(traceback.format_exc())