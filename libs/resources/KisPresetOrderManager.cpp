/*
 * SPDX-FileCopyrightText: 2026 Tenzin Rangdol tenzindraws@gmail.com
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KisPresetOrderManager.h"

#include <QStandardPaths>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDebug>
#include <QMutexLocker>

#include <kis_debug.h>

KisPresetOrderManager *KisPresetOrderManager::s_instance = nullptr;
QMutex KisPresetOrderManager::s_instanceMutex;

struct KisPresetOrderManager::Private
{
    // Map from tag URL to ordered list of resource IDs
    QMap<QString, QList<int>> orderByTag;
    mutable QMutex dataMutex;
    bool dirty {false};
};

KisPresetOrderManager::KisPresetOrderManager()
    : QObject(nullptr)
    , d(new Private)
{
    load();
}

KisPresetOrderManager::~KisPresetOrderManager()
{
    if (d->dirty) {
        save();
    }
    delete d;
}

KisPresetOrderManager *KisPresetOrderManager::instance()
{
    QMutexLocker locker(&s_instanceMutex);
    if (!s_instance) {
        s_instance = new KisPresetOrderManager();
    }
    return s_instance;
}

QString KisPresetOrderManager::configFilePath() const
{
    QString configPath = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
    QDir dir(configPath);
    if (!dir.exists()) {
        dir.mkpath(".");
    }
    return configPath + "/preset_order.json";
}

QList<int> KisPresetOrderManager::getOrderForTag(const QString &tagUrl) const
{
    QMutexLocker locker(&d->dataMutex);
    return d->orderByTag.value(tagUrl, QList<int>());
}

void KisPresetOrderManager::setOrderForTag(const QString &tagUrl, const QList<int> &resourceIds)
{
    {
        QMutexLocker locker(&d->dataMutex);
        d->orderByTag[tagUrl] = resourceIds;
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

int KisPresetOrderManager::getPosition(const QString &tagUrl, int resourceId) const
{
    QMutexLocker locker(&d->dataMutex);
    if (!d->orderByTag.contains(tagUrl)) {
        return -1;
    }
    return d->orderByTag[tagUrl].indexOf(resourceId);
}

bool KisPresetOrderManager::hasCustomOrder(const QString &tagUrl) const
{
    QMutexLocker locker(&d->dataMutex);
    return d->orderByTag.contains(tagUrl) && !d->orderByTag[tagUrl].isEmpty();
}

void KisPresetOrderManager::moveResource(const QString &tagUrl, int resourceId, int newPosition)
{
    {
        QMutexLocker locker(&d->dataMutex);
        QList<int> &order = d->orderByTag[tagUrl];

        int currentPos = order.indexOf(resourceId);
        if (currentPos < 0) {
            // Resource not in list, add it at the new position
            order.insert(qBound(0, newPosition, order.size()), resourceId);
        } else {
            // Remove from current position
            order.removeAt(currentPos);
            // Adjust target position if needed
            if (newPosition > currentPos) {
                newPosition--;
            }
            // Insert at new position
            order.insert(qBound(0, newPosition, order.size()), resourceId);
        }
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

void KisPresetOrderManager::moveResources(const QString &tagUrl, const QList<int> &resourceIds, int targetPosition)
{
    if (resourceIds.isEmpty()) return;

    {
        QMutexLocker locker(&d->dataMutex);
        QList<int> &order = d->orderByTag[tagUrl];

        // Track positions of resources being moved
        QList<int> positions;
        for (int id : resourceIds) {
            int pos = order.indexOf(id);
            if (pos >= 0) {
                positions.append(pos);
            }
        }

        // Sort positions in descending order for safe removal
        std::sort(positions.begin(), positions.end(), std::greater<int>());

        // Remove resources from their current positions
        for (int pos : positions) {
            order.removeAt(pos);
        }

        // Adjust target position based on removed items
        int removedBeforeTarget = 0;
        for (int pos : positions) {
            if (pos < targetPosition) {
                removedBeforeTarget++;
            }
        }
        targetPosition -= removedBeforeTarget;
        targetPosition = qBound(0, targetPosition, order.size());

        // Insert all resources at the target position
        for (int i = resourceIds.size() - 1; i >= 0; i--) {
            order.insert(targetPosition, resourceIds[i]);
        }
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

void KisPresetOrderManager::addNewResources(const QString &tagUrl, const QList<int> &resourceIds, const QStringList &resourceNames)
{
    if (resourceIds.isEmpty()) return;

    {
        QMutexLocker locker(&d->dataMutex);
        QList<int> &order = d->orderByTag[tagUrl];

        // Create pairs for sorting
        QList<QPair<QString, int>> pairs;
        for (int i = 0; i < resourceIds.size() && i < resourceNames.size(); i++) {
            // Only add if not already in order
            if (!order.contains(resourceIds[i])) {
                pairs.append(qMakePair(resourceNames[i].toLower(), resourceIds[i]));
            }
        }

        // Sort alphabetically by name
        std::sort(pairs.begin(), pairs.end(), [](const QPair<QString, int> &a, const QPair<QString, int> &b) {
            return a.first < b.first;
        });

        // Insert at the beginning (top) in sorted order
        for (int i = pairs.size() - 1; i >= 0; i--) {
            order.prepend(pairs[i].second);
        }
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

void KisPresetOrderManager::removeResource(const QString &tagUrl, int resourceId)
{
    {
        QMutexLocker locker(&d->dataMutex);
        if (!d->orderByTag.contains(tagUrl)) return;
        d->orderByTag[tagUrl].removeAll(resourceId);
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

void KisPresetOrderManager::clearOrderForTag(const QString &tagUrl)
{
    {
        QMutexLocker locker(&d->dataMutex);
        d->orderByTag.remove(tagUrl);
        d->dirty = true;
    }
    Q_EMIT orderChanged(tagUrl);
}

void KisPresetOrderManager::save()
{
    QMutexLocker locker(&d->dataMutex);

    QJsonObject root;

    for (auto it = d->orderByTag.constBegin(); it != d->orderByTag.constEnd(); ++it) {
        QJsonArray orderArray;
        for (int id : it.value()) {
            orderArray.append(id);
        }
        root[it.key()] = orderArray;
    }

    QJsonDocument doc(root);
    QFile file(configFilePath());
    if (file.open(QIODevice::WriteOnly)) {
        file.write(doc.toJson(QJsonDocument::Indented));
        file.close();
        d->dirty = false;
    } else {
        qWarning() << "KisPresetOrderManager: Could not save preset order to" << configFilePath();
    }
}

void KisPresetOrderManager::load()
{
    QMutexLocker locker(&d->dataMutex);

    QFile file(configFilePath());
    if (!file.exists()) {
        return;
    }

    if (!file.open(QIODevice::ReadOnly)) {
        qWarning() << "KisPresetOrderManager: Could not load preset order from" << configFilePath();
        return;
    }

    QJsonParseError error;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &error);
    file.close();

    if (error.error != QJsonParseError::NoError) {
        qWarning() << "KisPresetOrderManager: Parse error:" << error.errorString();
        return;
    }

    if (!doc.isObject()) {
        return;
    }

    QJsonObject root = doc.object();
    for (auto it = root.constBegin(); it != root.constEnd(); ++it) {
        QString tagUrl = it.key();
        QJsonArray orderArray = it.value().toArray();
        QList<int> order;
        for (const QJsonValue &val : orderArray) {
            order.append(val.toInt());
        }
        d->orderByTag[tagUrl] = order;
    }

    d->dirty = false;
}
