import sqlite3
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

# ==========================================
# 1. DATABASE & MODELS SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect("ai_social_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            topics TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

class AgentRegister(BaseModel):
    id: str
    name: str
    description: str
    topics: List[str]

class PostCreate(BaseModel):
    agent_id: str
    content: str


# ==========================================
# 2. PLATFORM ROUTING & NOTIFICATION ENGINE
# ==========================================
class AISocialNetworkPlatform:
    def register_agent(self, agent: AgentRegister):
        conn = sqlite3.connect("ai_social_network.db")
        cursor = conn.cursor()
        topics_str = ",".join(agent.topics)
        cursor.execute("INSERT OR REPLACE INTO agents (id, name, description, topics) VALUES (?, ?, ?, ?)",
                       (agent.id, agent.name, agent.description, topics_str))
        conn.commit()
        conn.close()
        print(f"[REGISTERED] Agent '{agent.name}' registered successfully.")

    def get_all_agents(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect("ai_social_network.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, topics FROM agents")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1], "description": r[2], "topics": r[3].split(",")} for r in rows]

    def route_and_notify(self, post_id: int, publisher_id: str, content: str) -> List[str]:
        """Core routing logic: Determines who finds the post relevant using semantic filtering."""
        all_agents = self.get_all_agents()
        notified_agents = []

        for agent in all_agents:
            if agent["id"] == publisher_id:
                continue
            if self._is_relevant(agent, content):
                notified_agents.append(agent["id"])
                print(f"   -> [NOTIFIED] Agent '{agent['id']}' matched and notified.")
        return notified_agents

    def _is_relevant(self, agent: Dict[str, Any], post_content: str) -> bool:
        """LLM-based relevance filter to avoid spam and missed matches."""
        prompt = f"""
        You are a relevance router for AI agents.
        Agent ID: {agent['id']}
        Description: {agent['description']}
        Interests: {', '.join(agent['topics'])}
        Post: "{post_content}"
        Is this post relevant to this agent? Answer ONLY with 'YES' or 'NO'.
        """
        try:
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return "YES" in res.choices[0].message.content.strip().upper()
        except Exception:
            return any(t.lower() in post_content.lower() for t in agent["topics"])

    def create_post(self, post: PostCreate):
        conn = sqlite3.connect("ai_social_network.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (agent_id, content) VALUES (?, ?)", (post.agent_id, post.content))
        post_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"\n[NEW POST] {post.agent_id} published: \"{post.content}\"")
        notified = self.route_and_notify(post_id, post.agent_id, post.content)
        self.trigger_responses(post_id, post.content, notified)

    def trigger_responses(self, post_id: int, content: str, notified_agents: List[str]):
        conn = sqlite3.connect("ai_social_network.db")
        cursor = conn.cursor()
        for agent_id in notified_agents:
            cursor.execute("SELECT name, description, topics FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if not row: continue
            name, desc, topics = row

            prompt = f"""
            You are {name} ({desc}). Topics: {topics}.
            Another agent posted: "{content}"
            Decide if you want to comment (e.g., offer a payment/discount tie-in). If yes, write a short comment. If no, reply 'PASS'.
            """
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.3)
            comment = res.choices[0].message.content.strip()
            if "PASS" not in comment:
                cursor.execute("INSERT INTO comments (post_id, agent_id, content) VALUES (?, ?, ?)", (post_id, agent_id, comment))
                conn.commit()
                print(f"      💬 [COMMENT] {name}: \"{comment}\"")
        conn.close()


# ==========================================
# 3. RUN SIMULATION
# ==========================================
if __name__ == "__main__":
    platform = AISocialNetworkPlatform()

    # Registering Agents
    platform.register_agent(AgentRegister(id="swiggy_agent", name="Swiggy Bot", description="Handles food delivery offers.", topics=["discounts", "food", "diwali"]))
    platform.register_agent(AgentRegister(id="phonepe_agent", name="PhonePe Bot", description="Manages UPI cashback and payment offers.", topics=["upi", "cashback", "payments", "diwali"]))
    platform.register_agent(AgentRegister(id="hdfc_agent", name="HDFC Bank Bot", description="Manages credit card discounts.", topics=["cards", "bank offers", "cashback"]))
    platform.register_agent(AgentRegister(id="bajaj_auto_agent", name="Bajaj Auto Bot", description="Manages two-wheeler vehicles.", topics=["vehicles", "bikes"]))

    # Test Run matching the assignment example: Swiggy posts a Diwali offer
    platform.create_post(PostCreate(agent_id="swiggy_agent", content="5% off all deliveries on Diwali."))