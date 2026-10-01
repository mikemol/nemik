// nemik:W121 (luthen-observability:W234): sync nemik-ics's VTODOs into the operator's Google Tasks
// list through Akonadi, so the OAuth token never leaves Akonadi/KWallet.
//
//   nemik-ics --opt-in ... | nemik-akonadi-tasks [--list NAME] [--create-list] [--apply]
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
#include <Akonadi/ItemFetchJob>
#include <Akonadi/ItemFetchScope>
#include <Akonadi/ItemModifyJob>
#include <KCalendarCore/ICalFormat>
#include <KCalendarCore/MemoryCalendar>
#include <KCalendarCore/Todo>
#include <QCoreApplication>
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
    const bool apply = args.contains(QStringLiteral("--apply"));
    const int li = args.indexOf(QStringLiteral("--list"));
    const QString listName = li > 0 && li + 1 < args.size() ? args.at(li + 1) : QString();

    // The feed: every VTODO nemik-ics wrote, keyed by ref; the description gains the ref tag.
    QTextStream in(stdin);
    auto feedCal = KCalendarCore::MemoryCalendar::Ptr(new KCalendarCore::MemoryCalendar(QTimeZone::utc()));
    KCalendarCore::ICalFormat fmt;
    if (!fmt.fromString(feedCal, in.readAll())) { out(QStringLiteral("ERROR: stdin is not iCalendar")); return 2; }
    QHash<QString, Todo::Ptr> feed;
    for (const Todo::Ptr &t : feedCal->rawTodos()) {
        const QString ref = refOf(t);
        if (ref.isEmpty()) continue;
        t->setDescription(t->description() + QLatin1Char('\n') + kRefTag + ref);
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
        if (have->summary() == want->summary() && have->description() == want->description()) continue;
        have->setSummary(want->summary());
        have->setDescription(want->description());
        item.setPayload<Todo::Ptr>(have);
        out(QStringLiteral("UPDATE ") + f.key() + QStringLiteral("  ") + want->summary());
        run(new Akonadi::ItemModifyJob(item), f.key());
    }
    for (auto m = mine.cbegin(); m != mine.cend(); ++m) {  // the ask closed upstream
        if (feed.contains(m.key())) continue;
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
