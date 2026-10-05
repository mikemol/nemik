// nemik:W121 (luthen-observability:W234): sync nemik-ics's VTODOs into the operator's Google Tasks
// list through Akonadi, so the OAuth token never leaves Akonadi/KWallet.
//
//   nemik-ics --opt-in ... | nemik-akonadi-tasks [--list NAME] [--create-list] [--apply]
//   nemik-akonadi-tasks --export-calendar NAME --out FILE.ics      (read-only; nemik:W147)
//
// Without --apply it only PLANS (prints CREATE/UPDATE/COMPLETE lines) and writes nothing.
// The collection is resolved by name, never by id (luthen): a child of akonadi_google_resource_0
// whose content type is application/x-vnd.akonadi.calendar.todo; --list picks one by name when
// there are several. --create-list (with --apply) creates the named list in the Google account when
// no list has that name (operator 2026-09-30: a dedicated "nemik" list). A task is nemik's when its UID is nemik:<repo>:W<n> OR its description carries
// "nemik-ref: <repo>:W<n>" (the Google resource may not keep our UID). The reverse direction is a
// claim, never a fact: a nemik task the operator completed while its ask is still open prints
// "DONE-CLAIM <repo>:W<n>", for the asking repo to verify from its own readings.
#include <Akonadi/Collection>
#include <Akonadi/CollectionCreateJob>
#include <Akonadi/CollectionFetchJob>
#include <Akonadi/Item>
#include <Akonadi/ItemCreateJob>
#include <Akonadi/ItemDeleteJob>
#include <Akonadi/ItemFetchJob>
#include <KCalendarCore/Alarm>
#include <Akonadi/ItemFetchScope>
#include <Akonadi/ItemModifyJob>
#include <KCalendarCore/ICalFormat>
#include <QSet>
#include <KCalendarCore/MemoryCalendar>
#include <KCalendarCore/Event>
#include <KCalendarCore/Todo>
#include <QDir>
#include <QFile>
#include <QSaveFile>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QTextStream>
#include <QTimeZone>
#include <cstdio>

using KCalendarCore::Todo;
static const QString kResource = QStringLiteral("akonadi_google_resource_0");
static const QString kTodoMime = QStringLiteral("application/x-vnd.akonadi.calendar.todo");
static const QString kRefTag = QStringLiteral("nemik-ref: ");

static QString refOf(const Todo::Ptr &t) {
    if (t->uid().startsWith(QStringLiteral("nemik:"))) return t->uid().mid(6);
    for (const QString &line : t->description().split(QLatin1Char('\n')))
        if (line.startsWith(kRefTag)) return line.mid(kRefTag.size()).trimmed();
    return {};
}

static void out(const QString &s) { std::fputs((s + QLatin1Char('\n')).toUtf8().constData(), stdout); }

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const QStringList args = app.arguments();
    // nemik:W193 (luthen-observability:W299): never start Akonadi from here. With no session bus, or
    // no running akonadi_control, the Akonadi client library goes looking for a server and spawns
    // akonadi_control itself; from an agent scope that process has no display and Qt aborts it
    // (core dumps 2026-10-02 13:33 and 2026-10-03 22:31 EDT, both in claude-nemik-*.scope, both at
    // moments this helper ran). Refuse first, before any Akonadi object exists.
    {
        auto bus = QDBusConnection::sessionBus();
        if (!bus.isConnected() || !bus.interface()
            || !bus.interface()->isServiceRegistered(QStringLiteral("org.freedesktop.Akonadi.Control"))) {
            out(QStringLiteral("ERROR: akonadi is not running on this session bus; refusing to start it from here"));
            return 2;
        }
    }
    const bool apply = args.contains(QStringLiteral("--apply"));
    // --only REF (repeatable): sync just these refs and leave every other task as it is (no COMPLETE
    // for refs outside the set), so a new mapping can be tried on one task (nemik:W162).
    QSet<QString> only;
    for (int i = 0; i + 1 < args.size(); ++i)
        if (args.at(i) == QStringLiteral("--only")) only.insert(args.at(i + 1));
    const int li = args.indexOf(QStringLiteral("--list"));
    const QString listName = li > 0 && li + 1 < args.size() ? args.at(li + 1) : QString();

    KCalendarCore::ICalFormat fmt;
    // nemik:W147: export one calendar's events to an .ics file for mikemol-ics (mtools:W304 split:
    // the Akonadi read is nemik's, so Qt stays out of mtools). Read-only on the account. The file
    // holds personal data: it is written 0600, atomically, and its contents are never printed.
    const int ei = args.indexOf(QStringLiteral("--export-calendar"));
    if (ei > 0) {
        const QString calName = ei + 1 < args.size() ? args.at(ei + 1) : QString();
        const int oi = args.indexOf(QStringLiteral("--out"));
        const QString outPath = oi > 0 && oi + 1 < args.size() ? args.at(oi + 1) : QString();
        static const QString kEventMime = QStringLiteral("application/x-vnd.akonadi.calendar.event");
        auto *ccj = new Akonadi::CollectionFetchJob(Akonadi::Collection::root(), Akonadi::CollectionFetchJob::Recursive);
        if (!ccj->exec()) { out(QStringLiteral("ERROR: collections: ") + ccj->errorString()); return 2; }
        QList<Akonadi::Collection> cals;
        for (const Akonadi::Collection &c : ccj->collections())
            if (c.resource() == kResource && c.contentMimeTypes().contains(kEventMime)
                && (c.displayName() == calName || c.name() == calName))
                cals << c;
        if (cals.size() != 1 || outPath.isEmpty()) {
            out(QStringLiteral("ERROR: %1 calendars named %2 (and --out is %3); calendars:")
                    .arg(cals.size()).arg(calName, outPath.isEmpty() ? QStringLiteral("missing") : QStringLiteral("set")));
            for (const Akonadi::Collection &c : ccj->collections())
                if (c.resource() == kResource && c.contentMimeTypes().contains(kEventMime)) out(QStringLiteral("  ") + c.displayName());
            return 2;
        }
        auto *eij = new Akonadi::ItemFetchJob(cals.first());
        eij->fetchScope().fetchFullPayload();
        if (!eij->exec()) { out(QStringLiteral("ERROR: items: ") + eij->errorString()); return 2; }
        auto cal = KCalendarCore::MemoryCalendar::Ptr(new KCalendarCore::MemoryCalendar(QTimeZone::utc()));
        int n = 0;
        for (const Akonadi::Item &it : eij->items())
            if (it.hasPayload<KCalendarCore::Incidence::Ptr>()) { cal->addIncidence(it.payload<KCalendarCore::Incidence::Ptr>()); ++n; }
        QDir().mkpath(QFileInfo(outPath).absolutePath());
        QSaveFile f(outPath);
        if (!f.open(QIODevice::WriteOnly)) { out(QStringLiteral("ERROR: cannot write ") + outPath); return 2; }
        f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
        f.write(fmt.toString(cal).toUtf8());
        if (!f.commit()) { out(QStringLiteral("ERROR: cannot write ") + outPath); return 2; }
        out(QStringLiteral("EXPORTED %1 incidences from %2").arg(n).arg(cals.first().displayName()));
        return 0;
    }

    // nemik:W195 (life's write ask): --rights [NAME] prints what the account lets nemik do to each
    // event calendar, from Akonadi's collection rights (they mirror Google's access role: owner and
    // writer may create/change/delete, reader may not). Read-only; metadata only, no event text.
    const int ri = args.indexOf(QStringLiteral("--rights"));
    if (ri > 0) {
        const QString only = ri + 1 < args.size() && !args.at(ri + 1).startsWith(QStringLiteral("--")) ? args.at(ri + 1) : QString();
        static const QString kEventMime2 = QStringLiteral("application/x-vnd.akonadi.calendar.event");
        auto *rcj = new Akonadi::CollectionFetchJob(Akonadi::Collection::root(), Akonadi::CollectionFetchJob::Recursive);
        if (!rcj->exec()) { out(QStringLiteral("ERROR: collections: ") + rcj->errorString()); return 2; }
        int n = 0;
        for (const Akonadi::Collection &c : rcj->collections()) {
            if (c.resource() != kResource || !c.contentMimeTypes().contains(kEventMime2)) continue;
            if (!only.isEmpty() && c.displayName() != only && c.name() != only) continue;
            const auto r = c.rights();
            auto yn = [&](Akonadi::Collection::Right f) { return r.testFlag(f) ? 'Y' : 'N'; };
            out(QStringLiteral("RIGHTS %1: create=%2 change=%3 delete=%4").arg(c.displayName())
                    .arg(QLatin1Char(yn(Akonadi::Collection::CanCreateItem)))
                    .arg(QLatin1Char(yn(Akonadi::Collection::CanChangeItem)))
                    .arg(QLatin1Char(yn(Akonadi::Collection::CanDeleteItem))));
            ++n;
        }
        if (n == 0) { out(QStringLiteral("ERROR: no event calendar matches")); return 2; }
        return 0;
    }

    // nemik:W198 (life's write ask): --write-calendar NAME [--apply] writes the VEVENTs on stdin
    // (nemik.calwrite's feed) INTO one event calendar. Three guards, in this order, each before any
    // write: (1) the account must hold create+change+delete on that calendar (Akonadi's collection
    // rights, which mirror Google's access role), else REFUSED and exit 2; (2) every event in the
    // feed must carry a nemik: UID, else REFUSED; (3) only events whose UID starts nemik: are ever
    // created, changed or deleted, so the operator's own events are untouched. Without --apply it
    // only PLANS. Output names refs and times, never titles.
    const int wi = args.indexOf(QStringLiteral("--write-calendar"));
    if (wi > 0) {
        const QString calName = wi + 1 < args.size() ? args.at(wi + 1) : QString();
        static const QString kEventMime3 = QStringLiteral("application/x-vnd.akonadi.calendar.event");
        static const QString kOwned = QStringLiteral("nemik:");
        auto *wcj = new Akonadi::CollectionFetchJob(Akonadi::Collection::root(), Akonadi::CollectionFetchJob::Recursive);
        if (!wcj->exec()) { out(QStringLiteral("ERROR: collections: ") + wcj->errorString()); return 2; }
        QList<Akonadi::Collection> targets;
        for (const Akonadi::Collection &c : wcj->collections())
            if (c.resource() == kResource && c.contentMimeTypes().contains(kEventMime3)
                && (c.displayName() == calName || c.name() == calName))
                targets << c;
        if (targets.size() != 1) {
            out(QStringLiteral("ERROR: %1 calendars named %2").arg(targets.size()).arg(calName));
            return 2;
        }
        const Akonadi::Collection target = targets.first();
        const auto rights = target.rights();
        if (!rights.testFlag(Akonadi::Collection::CanCreateItem) || !rights.testFlag(Akonadi::Collection::CanChangeItem)
            || !rights.testFlag(Akonadi::Collection::CanDeleteItem)) {
            out(QStringLiteral("REFUSED %1: this account has no write rights here (see --rights); nothing was written").arg(target.displayName()));
            return 2;
        }
        QTextStream wstdin(stdin);
        auto wfeed = KCalendarCore::MemoryCalendar::Ptr(new KCalendarCore::MemoryCalendar(QTimeZone::utc()));
        if (!fmt.fromString(wfeed, wstdin.readAll())) { out(QStringLiteral("ERROR: stdin is not iCalendar")); return 2; }
        auto eventRef = [&](const KCalendarCore::Incidence::Ptr &e) -> QString {
            if (e->uid().startsWith(kOwned)) return e->uid().mid(kOwned.size());
            for (const QString &line : e->description().split(QLatin1Char('\n')))
                if (line.startsWith(kRefTag)) return line.mid(kRefTag.size()).trimmed();
            return {};
        };
        QHash<QString, KCalendarCore::Event::Ptr> want;
        for (const KCalendarCore::Event::Ptr &e : wfeed->rawEvents()) {
            if (!e->uid().startsWith(kOwned)) {
                out(QStringLiteral("REFUSED: a feed event lacks a nemik: UID; nemik writes only its own events"));
                return 2;
            }
            want.insert(e->uid().mid(kOwned.size()), e);
        }
        auto *wij = new Akonadi::ItemFetchJob(target);
        wij->fetchScope().fetchFullPayload();
        if (!wij->exec()) { out(QStringLiteral("ERROR: items: ") + wij->errorString()); return 2; }
        QHash<QString, Akonadi::Item> have;  // nemik-owned events only
        for (const Akonadi::Item &it : wij->items()) {
            if (!it.hasPayload<KCalendarCore::Incidence::Ptr>()) continue;
            const auto inc = it.payload<KCalendarCore::Incidence::Ptr>();
            const QString r = eventRef(inc);
            if (!r.isEmpty() && (inc->uid().startsWith(kOwned) || inc->description().contains(kRefTag))) have.insert(r, it);
        }
        auto same = [](const KCalendarCore::Event::Ptr &a, const KCalendarCore::Event::Ptr &b) {
            if (a->summary() != b->summary() || a->description() != b->description() || a->allDay() != b->allDay()
                || a->dtStart() != b->dtStart() || a->dtEnd() != b->dtEnd() || !(*a->recurrence() == *b->recurrence())
                || a->alarms().size() != b->alarms().size())
                return false;
            for (int i = 0; i < a->alarms().size(); ++i)
                if (a->alarms().at(i)->startOffset() != b->alarms().at(i)->startOffset()
                    || a->alarms().at(i)->endOffset() != b->alarms().at(i)->endOffset())
                    return false;
            return true;
        };
        int wfailed = 0;
        auto wrun = [&](KJob *job, const QString &what) {
            if (!apply) { delete job; return; }
            if (!job->exec()) { ++wfailed; out(QStringLiteral("FAILED ") + what + QStringLiteral(": ") + job->errorString()); }
        };
        QStringList refs = want.keys();
        refs.sort();
        for (const QString &r : refs) {
            const KCalendarCore::Event::Ptr ev = want.value(r);
            const QString when = ev->dtStart().toString(Qt::ISODate);
            if (!have.contains(r)) {
                Akonadi::Item item(kEventMime3);
                item.setPayload<KCalendarCore::Incidence::Ptr>(ev);
                out(QStringLiteral("CREATE ") + r + QStringLiteral("  ") + when);
                wrun(new Akonadi::ItemCreateJob(item, target), r);
                continue;
            }
            Akonadi::Item item = have.value(r);
            const auto cur = item.payload<KCalendarCore::Incidence::Ptr>().dynamicCast<KCalendarCore::Event>();
            if (cur && same(cur, ev)) continue;
            // Keep the item's own identity (its UID as Google holds it) and replace the content.
            KCalendarCore::Event::Ptr next(ev->clone());
            if (cur) next->setUid(cur->uid());
            item.setPayload<KCalendarCore::Incidence::Ptr>(next);
            out(QStringLiteral("UPDATE ") + r + QStringLiteral("  ") + when);
            wrun(new Akonadi::ItemModifyJob(item), r);
        }
        QStringList stale = have.keys();
        stale.sort();
        for (const QString &r : stale) {  // a waypoint that is no longer open or dated
            if (want.contains(r)) continue;
            out(QStringLiteral("DELETE ") + r);
            wrun(new Akonadi::ItemDeleteJob(have.value(r)), r);
        }
        out(apply ? QStringLiteral("APPLIED (%1 failed)").arg(wfailed) : QStringLiteral("PLAN ONLY: rerun with --apply to write"));
        return wfailed ? 1 : 0;
    }

    // The feed: every VTODO nemik-ics wrote, keyed by ref; the description gains the ref tag.
    QTextStream in(stdin);
    auto feedCal = KCalendarCore::MemoryCalendar::Ptr(new KCalendarCore::MemoryCalendar(QTimeZone::utc()));
    if (!fmt.fromString(feedCal, in.readAll())) { out(QStringLiteral("ERROR: stdin is not iCalendar")); return 2; }
    QHash<QString, Todo::Ptr> feed;
    for (const Todo::Ptr &t : feedCal->rawTodos()) {
        const QString ref = refOf(t);
        if (ref.isEmpty()) continue;
        t->setDescription(t->description() + QLatin1Char('\n') + kRefTag + ref);
        if (!only.isEmpty() && !only.contains(ref)) continue;  // nemik:W162: try a change on chosen refs first
        feed.insert(ref, t);
    }

    auto *cj = new Akonadi::CollectionFetchJob(Akonadi::Collection::root(), Akonadi::CollectionFetchJob::Recursive);
    if (!cj->exec()) { out(QStringLiteral("ERROR: collections: ") + cj->errorString()); return 2; }
    QList<Akonadi::Collection> lists;
    for (const Akonadi::Collection &c : cj->collections())
        if (c.resource() == kResource && c.contentMimeTypes().contains(kTodoMime)
            && (listName.isEmpty() || c.displayName() == listName || c.name() == listName))
            lists << c;
    const bool create = args.contains(QStringLiteral("--create-list"));
    if (lists.isEmpty() && create && !listName.isEmpty()) {
        // The resource's top collection is the account; a child with the to-do type is a task list.
        Akonadi::Collection top;
        for (const Akonadi::Collection &c : cj->collections())
            if (c.resource() == kResource && c.parentCollection() == Akonadi::Collection::root()) top = c;
        if (!top.isValid()) { out(QStringLiteral("ERROR: no top collection for ") + kResource); return 2; }
        out(QStringLiteral("CREATE-LIST ") + listName);
        if (!apply) { out(QStringLiteral("PLAN ONLY: rerun with --apply to write")); return 0; }
        Akonadi::Collection c;
        c.setParentCollection(top);
        c.setName(listName);
        c.setContentMimeTypes({kTodoMime});
        auto *mk = new Akonadi::CollectionCreateJob(c);
        if (!mk->exec()) { out(QStringLiteral("ERROR: create list: ") + mk->errorString()); return 2; }
        lists << mk->collection();
    }
    if (lists.size() != 1) {
        out(QStringLiteral("ERROR: %1 task lists match; name one with --list:").arg(lists.size()));
        for (const Akonadi::Collection &c : cj->collections())
            if (c.resource() == kResource && c.contentMimeTypes().contains(kTodoMime)) out(QStringLiteral("  ") + c.displayName());
        return 2;
    }
    const Akonadi::Collection list = lists.first();
    out(QStringLiteral("LIST %1 (%2 asks in the feed)").arg(list.displayName()).arg(feed.size()));

    auto *ij = new Akonadi::ItemFetchJob(list);
    ij->fetchScope().fetchFullPayload();
    if (!ij->exec()) { out(QStringLiteral("ERROR: items: ") + ij->errorString()); return 2; }
    QHash<QString, Akonadi::Item> mine;
    for (const Akonadi::Item &it : ij->items()) {
        if (!it.hasPayload<Todo::Ptr>()) continue;
        const QString ref = refOf(it.payload<Todo::Ptr>());
        if (!ref.isEmpty()) mine.insert(ref, it);
        // nemik:W162: with --only, report what the list holds for those refs, parent included, so a
        // mapping can be read back after the resource syncs.
        if (only.contains(ref))
            out(QStringLiteral("HAVE %1 remote=%2 parent=%3").arg(ref, it.remoteId(), it.payload<Todo::Ptr>()->relatedTo(KCalendarCore::Incidence::RelTypeParent)));
    }

    // nemik:W162: Google's resource passes relatedTo(RelTypeParent) straight to TaskMoveJob as the
    // new parent's *Google task id* (kdepim-runtime taskhandler.cpp itemChanged). The feed names the
    // parent by its nemik UID, so translate it to the parent item's remoteId, which only exists once
    // the parent has been created on Google. Until then the child stays unparented this run.
    QHash<QString, QString> remoteOf;  // nemik UID -> Akonadi remoteId (the Google task id)
    // Keyed by ref: Google's resource does not keep our UID on the item, only the nemik-ref line.
    for (auto m = mine.cbegin(); m != mine.cend(); ++m) remoteOf.insert(QStringLiteral("nemik:") + m.key(), m.value().remoteId());
    for (const Todo::Ptr &t : feed) {
        const QString p = t->relatedTo(KCalendarCore::Incidence::RelTypeParent);
        if (p.isEmpty()) continue;
        t->setRelatedTo(remoteOf.value(p), KCalendarCore::Incidence::RelTypeParent);
        if (!remoteOf.contains(p)) out(QStringLiteral("DEFER-PARENT ") + refOf(t) + QStringLiteral(" (parent not on Google yet; rerun)"));
    }

    int failed = 0;
    auto run = [&](KJob *job, const QString &what) {
        if (!apply) { delete job; return; }
        if (!job->exec()) { ++failed; out(QStringLiteral("FAILED ") + what + QStringLiteral(": ") + job->errorString()); }
    };
    for (auto f = feed.cbegin(); f != feed.cend(); ++f) {
        const Todo::Ptr want = f.value();
        if (!mine.contains(f.key())) {
            Akonadi::Item item(kTodoMime);
            item.setPayload<Todo::Ptr>(want);
            out(QStringLiteral("CREATE ") + f.key() + QStringLiteral("  ") + want->summary());
            run(new Akonadi::ItemCreateJob(item, list), f.key());
            continue;
        }
        Akonadi::Item item = mine.value(f.key());
        const Todo::Ptr have = item.payload<Todo::Ptr>();
        if (have->isCompleted()) { out(QStringLiteral("DONE-CLAIM ") + f.key()); continue; }
        // nemik:W134: start and due times (mtools:W300) sync too, so a moved date moves the task.
        if (have->summary() == want->summary() && have->description() == want->description()
            && have->dtStart() == want->dtStart() && have->dtDue() == want->dtDue()
            && have->relatedTo(KCalendarCore::Incidence::RelTypeParent) == want->relatedTo(KCalendarCore::Incidence::RelTypeParent))
            continue;
        // nemik:W148/W162: the parent (RELATED-TO;RELTYPE=PARENT) moves too, re-parenting in place.
        have->setRelatedTo(want->relatedTo(KCalendarCore::Incidence::RelTypeParent), KCalendarCore::Incidence::RelTypeParent);
        have->setSummary(want->summary());
        have->setDescription(want->description());
        have->setDtStart(want->dtStart());
        have->setDtDue(want->dtDue());
        item.setPayload<Todo::Ptr>(have);
        out(QStringLiteral("UPDATE ") + f.key() + QStringLiteral("  ") + want->summary());
        run(new Akonadi::ItemModifyJob(item), f.key());
    }
    for (auto m = mine.cbegin(); m != mine.cend(); ++m) {  // the ask closed upstream
        if (feed.contains(m.key()) || (!only.isEmpty() && !only.contains(m.key()))) continue;
        Akonadi::Item item = m.value();
        const Todo::Ptr have = item.payload<Todo::Ptr>();
        if (have->isCompleted()) continue;
        have->setCompleted(QDateTime::currentDateTimeUtc());
        item.setPayload<Todo::Ptr>(have);
        out(QStringLiteral("COMPLETE ") + m.key());
        run(new Akonadi::ItemModifyJob(item), m.key());
    }
    out(apply ? QStringLiteral("APPLIED (%1 failed)").arg(failed) : QStringLiteral("PLAN ONLY: rerun with --apply to write"));
    return failed ? 1 : 0;
}
