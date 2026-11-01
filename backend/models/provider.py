"""Internet providers (ISPs and mobile carriers) and the networks (ASNs) they operate."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class Provider(db.Model):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    # "mobile", "broadband" or "both"
    kind: Mapped[str] = mapped_column(String(16))

    asns: Mapped[list["ProviderASN"]] = relationship(back_populates="provider", cascade="all, delete-orphan",
                                                     order_by="ProviderASN.asn")

    def to_summary(self) -> dict:
        return {"slug": self.slug, "name": self.name, "kind": self.kind}


class ProviderASN(db.Model):
    """An Autonomous System Number: a block of IP networks run by one organisation."""
    __tablename__ = "provider_asns"

    asn: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)

    provider: Mapped[Provider] = relationship(back_populates="asns")
