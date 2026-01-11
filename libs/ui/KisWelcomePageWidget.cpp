
/* This file is part of the KDE project
 * SPDX-FileCopyrightText: 2018 Scott Petrovic <scottpetrovic@gmail.com>
 * SPDX-FileCopyrightText: 2021 L. E. Segovia <amy@amyspark.me>
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KisWelcomePageWidget.h"
#include "KisRecentDocumentsModelWrapper.h"
#include <QDesktopServices>
#include <QFileInfo>
#include <QMimeData>
#include <QPixmap>
#include <QImage>
#include <QMessageBox>
#include <QTemporaryFile>
#include <QByteArray>
#include <QBuffer>
#include <QNetworkAccessManager>
#include <QEventLoop>
#include <QDomDocument>

#include "KisRemoteFileFetcher.h"
#include "kactioncollection.h"
#include "kis_action.h"
#include "kis_action_manager.h"
#include <KisMimeDatabase.h>
#include <KisApplication.h>

#include "KConfigGroup"
#include "KSharedConfig"

#include <QListWidget>
#include <QListWidgetItem>
#include <QMenu>
#include <QScrollBar>
#include <QStyledItemDelegate>

#include "kis_icon_utils.h"
#include <kis_painting_tweaks.h>
#include "KoStore.h"
#include "kis_config.h"
#include "KisDocument.h"
#include <kis_image.h>
#include <kis_paint_device.h>
#include <KisPart.h>
#include <KisKineticScroller.h>
#include "KisMainWindow.h"

#include <QCoreApplication>
#include <kis_debug.h>
#include <QDir>

#include <klocalizedstring.h>
#include <KritaVersionWrapper.h>

#include <kis_config.h>
#include <kis_image_config.h>
#include "opengl/kis_opengl.h"

#ifdef Q_OS_MACOS
#include "libs/macosutils/KisMacosEntitlements.h"
#endif

// class to override item height for Breeze since qss seems to not work
class RecentItemDelegate : public QStyledItemDelegate
{
    int itemHeight = 0;
public:
    RecentItemDelegate(QObject *parent = 0)
        : QStyledItemDelegate(parent)
    {
    }

    void setItemHeight(int itemHeight)
    {
        this->itemHeight = itemHeight;
    }

    QSize sizeHint(const QStyleOptionViewItem &option, const QModelIndex &/*index*/) const override
    {
        return QSize(option.rect.width(), itemHeight);
    }
};


KisWelcomePageWidget::KisWelcomePageWidget(QWidget *parent)
    : QWidget(parent)
{
    setupUi(this);

    // URLs that go to web browser...
    devBuildIcon->setIcon(KisIconUtils::loadIcon("warning"));
    devBuildLabel->setVisible(false);
    // updaterFrame->setVisible(false);
    // versionNotificationLabel->setVisible(false);
    // bnVersionUpdate->setVisible(false);
    // bnErrorDetails->setVisible(false);

    // Recent docs...
    recentDocumentsListView->setDragEnabled(false);
    recentDocumentsListView->viewport()->setAutoFillBackground(false);
    recentDocumentsListView->setSpacing(2);
    recentDocumentsListView->installEventFilter(this);
    recentDocumentsListView->setViewMode(QListView::IconMode);
    recentDocumentsListView->setSelectionMode(QAbstractItemView::NoSelection);

//    m_recentItemDelegate.reset(new RecentItemDelegate(this));
//    m_recentItemDelegate->setItemHeight(KisRecentDocumentsModelWrapper::ICON_SIZE_LENGTH);
//    recentDocumentsListView->setItemDelegate(m_recentItemDelegate.data());
    recentDocumentsListView->setIconSize(QSize(KisRecentDocumentsModelWrapper::ICON_SIZE_LENGTH, KisRecentDocumentsModelWrapper::ICON_SIZE_LENGTH));
    recentDocumentsListView->setVerticalScrollMode(QListView::ScrollPerPixel);
    recentDocumentsListView->verticalScrollBar()->setSingleStep(50);
    {
        QScroller* scroller = KisKineticScroller::createPreconfiguredScroller(recentDocumentsListView);
        if (scroller) {
            connect(scroller, SIGNAL(stateChanged(QScroller::State)), this, SLOT(slotScrollerStateChanged(QScroller::State)));
        }
    }
    recentDocumentsListView->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(recentDocumentsListView, SIGNAL(customContextMenuRequested(QPoint)), SLOT(slotRecentDocContextMenuRequest(QPoint)));

    labelSupportText->setFont(largerFont());


    // Drop area..
    setAcceptDrops(true);
}

KisWelcomePageWidget::~KisWelcomePageWidget()
{
}

void KisWelcomePageWidget::setMainWindow(KisMainWindow* mainWin)
{
    if (mainWin) {
        m_mainWindow = mainWin;

        // set the shortcut links from actions (only if a shortcut exists)
        if ( mainWin->viewManager()->actionManager()->actionByName("file_new")->shortcut().toString() != "") {
            newFileLinkShortcut->setText(
                QString("(") + mainWin->viewManager()->actionManager()->actionByName("file_new")->shortcut().toString(QKeySequence::NativeText) + QString(")"));
        }
        if (mainWin->viewManager()->actionManager()->actionByName("file_open")->shortcut().toString()  != "") {
            openFileShortcut->setText(
                QString("(") + mainWin->viewManager()->actionManager()->actionByName("file_open")->shortcut().toString(QKeySequence::NativeText) + QString(")"));
        }
        connect(recentDocumentsListView, SIGNAL(clicked(QModelIndex)), this, SLOT(recentDocumentClicked(QModelIndex)));
        // we need the view manager to actually call actions, so don't create the connections
        // until after the view manager is set
        connect(newFileLink, SIGNAL(clicked(bool)), this, SLOT(slotNewFileClicked()));
        connect(openFileLink, SIGNAL(clicked(bool)), this, SLOT(slotOpenFileClicked()));
        connect(clearRecentFilesLink, SIGNAL(clicked(bool)), mainWin, SLOT(clearRecentFiles()));

        slotUpdateThemeColors();

        KisRecentDocumentsModelWrapper *recentFilesModel = KisRecentDocumentsModelWrapper::instance();
        connect(recentFilesModel, SIGNAL(sigModelIsUpToDate()), this, SLOT(slotRecentFilesModelIsUpToDate()));
        recentDocumentsListView->setModel(&recentFilesModel->model());
        slotRecentFilesModelIsUpToDate();
    }
}


void KisWelcomePageWidget::showDropAreaIndicator(bool show)
{
    if (!show) {
        QString dropFrameStyle = QStringLiteral("QFrame#dropAreaIndicator { border: 2px solid transparent }");
        dropFrameBorder->setStyleSheet(dropFrameStyle);
    } else {
        QColor textColor = qApp->palette().color(QPalette::Text);
        QColor backgroundColor = qApp->palette().color(QPalette::Window);
        QColor blendedColor = KisPaintingTweaks::blendColors(textColor, backgroundColor, 0.8);

        // QColor.name() turns it into a hex/web format
        QString dropFrameStyle = QString("QFrame#dropAreaIndicator { border: 2px dotted ").append(blendedColor.name()).append(" }") ;
        dropFrameBorder->setStyleSheet(dropFrameStyle);
    }
}

void KisWelcomePageWidget::slotUpdateThemeColors()
{
    textColor = qApp->palette().color(QPalette::Text);
    backgroundColor = qApp->palette().color(QPalette::Window);

    // make the welcome screen labels a subtle color so it doesn't clash with the main UI elements
    blendedColor = KisPaintingTweaks::blendColors(textColor, backgroundColor, 0.8);
    // only apply color to the widget itself, not to the tooltip or something
    blendedStyle = "QWidget{color: " + blendedColor.name() + "}";

    // what labels to change the color...
    startTitleLabel->setStyleSheet(blendedStyle);
    recentDocumentsLabel->setStyleSheet(blendedStyle);
    helpTitleLabel->setStyleSheet(blendedStyle);
    newFileLinkShortcut->setStyleSheet(blendedStyle);
    openFileShortcut->setStyleSheet(blendedStyle);
    clearRecentFilesLink->setStyleSheet(blendedStyle);
    recentDocumentsListView->setStyleSheet(blendedStyle);

#ifdef Q_OS_ANDROID
    blendedStyle = blendedStyle + "\nQPushButton { padding: 10px }";
#endif

    newFileLink->setStyleSheet(blendedStyle);
    openFileLink->setStyleSheet(blendedStyle);

    // make drop area QFrame have a dotted line
    dropFrameBorder->setObjectName("dropAreaIndicator");
    QString dropFrameStyle = QString("QFrame#dropAreaIndicator { border: 4px dotted ").append(blendedColor.name()).append("}");
    dropFrameBorder->setStyleSheet(dropFrameStyle);

    // only show drop area when we have a document over the empty area
    showDropAreaIndicator(false);

    // add icons for new and open settings to make them stand out a bit more
    openFileLink->setIconSize(QSize(48, 48));
    newFileLink->setIconSize(QSize(48, 48));

    openFileLink->setIcon(KisIconUtils::loadIcon("document-open"));
    newFileLink->setIcon(KisIconUtils::loadIcon("document-new"));

    supportKritaIcon->setIcon(KisIconUtils::loadIcon(QStringLiteral("support-krita")));
    const QIcon &linkIcon = KisIconUtils::loadIcon(QStringLiteral("bookmarks"));
    userManualIcon->setIcon(linkIcon);
    gettingStartedIcon->setIcon(linkIcon);
    userCommunityIcon->setIcon(linkIcon);
    kritaWebsiteIcon->setIcon(linkIcon);
    sourceCodeIcon->setIcon(linkIcon);

    kdeIcon->setIcon(KisIconUtils::loadIcon(QStringLiteral("kde")));

    // HTML links seem to be a bit more stubborn with theme changes... setting inline styles to help with color change
    userCommunityLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://krita-artists.org\">")
                               .append(i18n("User Community")).append("</a>"));

    gettingStartedLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://docs.krita.org/user_manual/getting_started.html\">")
                                .append(i18n("Getting Started")).append("</a>"));

    manualLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://docs.krita.org\">")
                        .append(i18n("User Manual")).append("</a>"));

    supportKritaLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://krita.org/support-us/donations?" + analyticsString + "donations" + "\">")
                              .append(i18n("Support Krita")).append("</a>"));

    kritaWebsiteLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://www.krita.org?" + analyticsString + "marketing-site" + "\">")
                              .append(i18n("Krita Website")).append("</a>"));

    sourceCodeLink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://invent.kde.org/graphics/krita\">")
                            .append(i18n("Source Code")).append("</a>"));

    poweredByKDELink->setText(QString("<a style=\"color: " + blendedColor.name() + " \" href=\"https://userbase.kde.org/What_is_KDE\">")
                              .append(i18n("Powered by KDE")).append("</a>"));

    const QColor faintTextColor = KisPaintingTweaks::blendColors(textColor, backgroundColor, 0.4);
    const QString &faintTextStyle = "QWidget{color: " + faintTextColor.name() + "}";
    labelNoRecentDocs->setStyleSheet(faintTextStyle);

    const QColor frameColor = KisPaintingTweaks::blendColors(textColor, backgroundColor, 0.1);
    const QString &frameQss = "{border: 1px solid " + frameColor.name() + "}";
    recentDocsStackedWidget->setStyleSheet("QStackedWidget#recentDocsStackedWidget" + frameQss);

    // show the dev version labels, if dev version is detected
    showDevVersionHighlight();

#ifdef Q_OS_MACOS
    // macOS store version should not contain external links containing donation buttons or forms
    if (KisMacosEntitlements().sandbox()) {
        supportKritaLink->hide();
        supportKritaIcon->hide();
        labelSupportText->hide();
        kritaWebsiteLink->hide();
        kritaWebsiteIcon->hide();
    }
#endif
}

void KisWelcomePageWidget::dragEnterEvent(QDragEnterEvent *event)
{
    showDropAreaIndicator(true);
    if (event->mimeData()->hasUrls() ||
        event->mimeData()->hasFormat("application/x-krita-node-internal-pointer") ||
        event->mimeData()->hasFormat("application/x-qt-image")) {
        return event->accept();
    }

    return event->ignore();
}

void KisWelcomePageWidget::dropEvent(QDropEvent *event)
{
    showDropAreaIndicator(false);

    if (event->mimeData()->hasUrls() && !event->mimeData()->urls().empty()) {
        Q_FOREACH (const QUrl &url, event->mimeData()->urls()) {
            if (url.toLocalFile().endsWith(".bundle", Qt::CaseInsensitive)) {
                bool r = m_mainWindow->installBundle(url.toLocalFile());
                if (!r) {
                    qWarning() << "Could not install bundle" << url.toLocalFile();
                }
            } else if (!url.isLocalFile()) {
                QScopedPointer<QTemporaryFile> tmp(new QTemporaryFile());
                tmp->setFileName(url.fileName());

                KisRemoteFileFetcher fetcher;

                if (!fetcher.fetchFile(url, tmp.data())) {
                    qWarning() << "Fetching" << url << "failed";
                    continue;
                }
                const auto localUrl = QUrl::fromLocalFile(tmp->fileName());

                m_mainWindow->openDocument(localUrl.toLocalFile(), KisMainWindow::None);
            } else {
                m_mainWindow->openDocument(url.toLocalFile(), KisMainWindow::None);
            }
        }
    }
}

void KisWelcomePageWidget::dragMoveEvent(QDragMoveEvent *event)
{
    m_mainWindow->dragMoveEvent(event);

    if (event->mimeData()->hasUrls() ||
        event->mimeData()->hasFormat("application/x-krita-node-internal-pointer") ||
        event->mimeData()->hasFormat("application/x-qt-image")) {
        return event->accept();
    }

    return event->ignore();
}

void KisWelcomePageWidget::dragLeaveEvent(QDragLeaveEvent */*event*/)
{
    showDropAreaIndicator(false);
    m_mainWindow->dragLeave();
}

void KisWelcomePageWidget::changeEvent(QEvent *event)
{
    if (event->type() == QEvent::FontChange) {
        labelSupportText->setFont(largerFont());
    }
}

bool KisWelcomePageWidget::eventFilter(QObject *watched, QEvent *event)
{
    if (watched == recentDocumentsListView && event->type() == QEvent::Leave) {
        recentDocumentsListView->clearSelection();
    }
    return QWidget::eventFilter(watched, event);
}

void KisWelcomePageWidget::showDevVersionHighlight()
{
    // always flag development version
    if (isDevelopmentBuild()) {
        QString devBuildLabelText = QString("<a style=\"color: " +
                                           blendedColor.name() +
                                           " \" href=\"https://docs.krita.org/en/untranslatable_pages/triaging_bugs.html?"
                                           + analyticsString + "dev-build" + "\">")
                                  .append(i18n("DEV BUILD")).append("</a>");

        devBuildLabel->setText(devBuildLabelText);
        devBuildIcon->setVisible(true);
        devBuildLabel->setVisible(true);
    } else {
        devBuildIcon->setVisible(false);
        devBuildLabel->setVisible(false);
    }
}

void KisWelcomePageWidget::recentDocumentClicked(QModelIndex index)
{
    QString fileUrl = index.data(Qt::ToolTipRole).toString();
    m_mainWindow->openDocument(fileUrl, KisMainWindow::None );
}

void KisWelcomePageWidget::slotRecentDocContextMenuRequest(const QPoint &pos)
{
    QMenu contextMenu;
    QModelIndex index = recentDocumentsListView->indexAt(pos);
    QAction *actionForget = 0;
    if (index.isValid()) {
        actionForget = new QAction(i18n("Forget \"%1\"", index.data(Qt::DisplayRole).toString()), &contextMenu);
        contextMenu.addAction(actionForget);
    }
    QAction *triggered = contextMenu.exec(recentDocumentsListView->mapToGlobal(pos));

    if (index.isValid() && triggered == actionForget) {
        m_mainWindow->removeRecentFile(index.data(Qt::ToolTipRole).toString());
    }
}

bool KisWelcomePageWidget::isDevelopmentBuild()
{
    return KritaVersionWrapper::isDevelopersBuild();
}

void KisWelcomePageWidget::slotNewFileClicked()
{
    m_mainWindow->slotFileNew();
}

void KisWelcomePageWidget::slotOpenFileClicked()
{
    m_mainWindow->slotFileOpen();
}

void KisWelcomePageWidget::slotRecentFilesModelIsUpToDate()
{
    KisRecentDocumentsModelWrapper *recentFilesModel = KisRecentDocumentsModelWrapper::instance();
    const bool modelIsEmpty = recentFilesModel->model().rowCount() == 0;

    if (modelIsEmpty) {
        recentDocsStackedWidget->setCurrentWidget(labelNoRecentDocs);
    } else {
        recentDocsStackedWidget->setCurrentWidget(recentDocumentsListView);
    }
    clearRecentFilesLink->setVisible(!modelIsEmpty);
}

QFont KisWelcomePageWidget::largerFont()
{
    QFont larger = font();
    larger.setPointSizeF(larger.pointSizeF() * 1.1f);
    return larger;
}
