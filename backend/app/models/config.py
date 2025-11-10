"""
Configuration model for storing application settings in database
"""

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base, utc_now


class Config(Base):
    """Configuration key-value store"""

    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return (
            f"<Config(key={self.key}, value={self.value[:50] if self.value else None})>"
        )
