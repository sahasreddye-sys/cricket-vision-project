"""Relational schema (SQLAlchemy 2.0). Works on SQLite and PostgreSQL."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="player")        # admin | coach | player
    player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Team(Base):
    """Single-row table holding the team's settings."""
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    season: Mapped[str] = mapped_column(String(20), default="")
    default_overs: Mapped[int] = mapped_column(Integer, default=20)
    speed_unit: Mapped[str] = mapped_column(String(8), default="kmh")


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    side: Mapped[str] = mapped_column(String(120), default="us", index=True)   # "us" or the opposition team's name
    role: Mapped[str] = mapped_column(String(20), default="batter")            # batter | bowler | all_rounder | wicket_keeper
    batting_hand: Mapped[str] = mapped_column(String(10), default="right")
    bowl_style: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)   # pace_fast | pace_medium | spin_off | spin_leg
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)            # synthetic demo data
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    opponent: Mapped[str] = mapped_column(String(120))
    venue: Mapped[str] = mapped_column(String(120), default="")
    format: Mapped[str] = mapped_column(String(20), default="T20")
    overs: Mapped[int] = mapped_column(Integer, default=20)
    season: Mapped[str] = mapped_column(String(20), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")      # scheduled | live | completed
    result: Mapped[str] = mapped_column(String(200), default="")
    outcome: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)   # won | lost | tied | no_result
    notes: Mapped[str] = mapped_column(Text, default="")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    innings: Mapped[list["Innings"]] = relationship(back_populates="match", cascade="all, delete-orphan",
                                                    order_by="Innings.number")


class Innings(Base):
    __tablename__ = "innings"
    __table_args__ = (UniqueConstraint("match_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    batting_side: Mapped[str] = mapped_column(String(10), default="us")       # us | them
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    match: Mapped[Match] = relationship(back_populates="innings")
    balls: Mapped[list["Ball"]] = relationship(cascade="all, delete-orphan", order_by="Ball.seq")
    batting_lines: Mapped[list["BattingLine"]] = relationship(cascade="all, delete-orphan")
    bowling_lines: Mapped[list["BowlingLine"]] = relationship(cascade="all, delete-orphan")


class Ball(Base):
    __tablename__ = "balls"
    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    non_striker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    bowler_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    runs_bat: Mapped[int] = mapped_column(Integer, default=0)
    wides: Mapped[int] = mapped_column(Integer, default=0)
    no_balls: Mapped[int] = mapped_column(Integer, default=0)
    byes: Mapped[int] = mapped_column(Integer, default=0)
    leg_byes: Mapped[int] = mapped_column(Integer, default=0)
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    wicket_kind: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    player_out_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    fielder_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    new_batter_on_strike: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # optional analysis fields
    bowl_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)      # pace | spin
    x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)                 # pitching point, metres
    y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shot_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    shot_angle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)        # wagon-wheel angle, degrees


class BattingLine(Base):
    """Scorecard-only entry for innings that were not scored ball by ball."""
    __tablename__ = "batting_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    balls: Mapped[int] = mapped_column(Integer, default=0)
    fours: Mapped[int] = mapped_column(Integer, default=0)
    sixes: Mapped[int] = mapped_column(Integer, default=0)
    out: Mapped[bool] = mapped_column(Boolean, default=True)
    how_out: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)


class BowlingLine(Base):
    __tablename__ = "bowling_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    legal_balls: Mapped[int] = mapped_column(Integer, default=0)
    maidens: Mapped[int] = mapped_column(Integer, default=0)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    wickets: Mapped[int] = mapped_column(Integer, default=0)
    wides: Mapped[int] = mapped_column(Integer, default=0)
    no_balls: Mapped[int] = mapped_column(Integer, default=0)


class SpeedReading(Base):
    __tablename__ = "speed_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(12), default="stopwatch")   # stopwatch | radar | video
    distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kmh: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(200), default="")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class BowlingSession(Base):
    __tablename__ = "bowling_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120), default="")
    target_x: Mapped[float] = mapped_column(Float, default=0.2)
    target_y: Mapped[float] = mapped_column(Float, default=7.0)
    tol_x: Mapped[float] = mapped_column(Float, default=0.2)
    tol_y: Mapped[float] = mapped_column(Float, default=1.0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    deliveries: Mapped[list["Delivery"]] = relationship(cascade="all, delete-orphan", order_by="Delivery.id")


class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("bowling_sessions.id", ondelete="CASCADE"), index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    bounced: Mapped[bool] = mapped_column(Boolean, default=True)


class FieldingEvent(Base):
    __tablename__ = "fielding_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"), nullable=True)
    date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer, default=1)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)


class FieldSetup(Base):
    __tablename__ = "field_setups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    style: Mapped[str] = mapped_column(String(20), default="balanced")
    positions: Mapped[list] = mapped_column(JSON)          # [{name, angle, distance}]
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class TrainingLog(Base):
    __tablename__ = "training_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(30))          # batting | bowling | fielding | fitness | match
    duration_min: Mapped[int] = mapped_column(Integer, default=0)
    intensity: Mapped[int] = mapped_column(Integer, default=3)    # 1-5, self-reported
    notes: Mapped[str] = mapped_column(Text, default="")


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    metric: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)     # e.g. max_speed, batting_average
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    due_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")              # open | achieved | dropped
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    achieved_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)


class VideoAnalysis(Base):
    __tablename__ = "video_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))           # bowling | batting | catching | tracking
    filename: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="ok")
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class DrsReview(Base):
    __tablename__ = "drs_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    inputs: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(20))
    lbw: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


def make_engine(url: Optional[str] = None):
    url = url or settings.database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _fk_on(conn, _):          # SQLite only enforces foreign keys when asked to
            conn.execute("PRAGMA foreign_keys=ON")
    return eng


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
