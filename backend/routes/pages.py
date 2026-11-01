"""Public HTML pages and the shared navigation."""
from typing import NamedTuple

from flask import Blueprint, render_template


pages = Blueprint("pages", __name__)


class NavItem(NamedTuple):
    endpoint: str
    label: str        # full label (desktop top bar)
    short_label: str  # compact label (mobile bottom bar)
    icon: str


NAV_ITEMS = (
    NavItem("pages.home", "Home", "Home", "home"),
    NavItem("pages.explore_map", "Explore India", "Explore", "map"),
    NavItem("pages.speed_test", "Speed Test", "Test", "gauge"),
    NavItem("pages.compare_providers", "Compare Providers", "Compare", "compare"),
    NavItem("pages.insights", "Insights", "Insights", "insights"),
)
SECONDARY_NAV_ITEMS = (
    NavItem("pages.about", "About SpeedSpot", "About", "info"),
    NavItem("pages.how_it_works", "How it works", "How it works", "steps"),
    NavItem("pages.privacy", "Privacy", "Privacy", "shield"),
)


@pages.app_context_processor
def inject_globals():
    return {"nav_items": NAV_ITEMS, "secondary_nav_items": SECONDARY_NAV_ITEMS}


@pages.get("/")
def home():
    return render_template("home.html", page_title="Home", page_script="home")


@pages.get("/map")
def explore_map():
    return render_template("map.html", page_title="Explore India", page_script="map", full_bleed=True)


@pages.get("/speed-test")
def speed_test():
    return render_template("speedtest.html", page_title="Speed Test", page_script="speedtest")


@pages.get("/providers")
def compare_providers():
    return render_template("providers.html", page_title="Compare Providers", page_script="providers")


@pages.get("/insights")
def insights():
    return render_template("insights.html", page_title="Insights", page_script="insights")


@pages.get("/about")
def about():
    return render_template("about.html", page_title="About SpeedSpot")


@pages.get("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html", page_title="How it works")


@pages.get("/privacy")
def privacy():
    return render_template("privacy.html", page_title="Privacy")
