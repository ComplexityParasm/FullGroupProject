#include <filesystem>
#include <sqlite3.h>
#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <nlohmann/json.hpp> // Подключение библиотеки для работы с JSON

using json = nlohmann::json;

class DatabaseManager {
public:
    DatabaseManager(const std::string& dbName) {
        std::cout << "Путь к базе данных: " << std::filesystem::absolute(dbName) << "\n";
        if (sqlite3_open(dbName.c_str(), &db) != SQLITE_OK) {
            std::cerr << "Ошибка открытия базы данных: " << sqlite3_errmsg(db) << std::endl;
            db = nullptr;
        } else {
            std::cerr << "База данных успешно открыта: " << dbName << std::endl;
        }
    }

    ~DatabaseManager() {
        if (db) {
            sqlite3_close(db);
            std::cerr << "База данных закрыта." << std::endl;
        }
    }

    bool createTable() {
        const char* createTableSQL =
            "CREATE TABLE IF NOT EXISTS tests ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name TEXT NOT NULL,"
            "questions TEXT NOT NULL,"
            "creator TEXT NOT NULL);";

        char* errMsg = nullptr;
        if (sqlite3_exec(db, createTableSQL, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            std::cerr << "Ошибка создания таблицы: " << errMsg << std::endl;
            sqlite3_free(errMsg);
            return false;
        }
        std::cerr << "Таблица 'tests' успешно создана или уже существует." << std::endl;
        return true;
    }

    bool insertTest(const std::string& name, const std::vector<std::string>& questions, const std::string& creator) {
        std::string questionsSerialized;
        for (const auto& question : questions) {
            questionsSerialized += question + ";";
        }

        const char* insertSQL = "INSERT INTO tests (name, questions, creator) VALUES (?, ?, ?);";
        sqlite3_stmt* stmt;

        if (sqlite3_prepare_v2(db, insertSQL, -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Ошибка подготовки запроса: " << sqlite3_errmsg(db) << std::endl;
            return false;
        }

        sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, questionsSerialized.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 3, creator.c_str(), -1, SQLITE_STATIC);

        if (sqlite3_step(stmt) != SQLITE_DONE) {
            std::cerr << "Ошибка выполнения запроса: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_finalize(stmt);
            return false;
        }

        sqlite3_finalize(stmt);
        std::cerr << "Тест успешно добавлен в базу данных." << std::endl;
        return true;
    }

private:
    sqlite3* db;
};

int main() {
    // Читаем JSON из stdin
    std::string inputJson;
    std::getline(std::cin, inputJson);

    std::cerr << "Полученный JSON: " << inputJson << std::endl;

    // Парсинг JSON
    json root;
    try {
        root = json::parse(inputJson);
    } catch (const json::parse_error& e) {
        std::cerr << "Ошибка парсинга JSON: " << e.what() << std::endl;
        return 1;
    }

    // Извлечение данных из JSON
    std::string testName;
    std::vector<std::string> questions;
    std::string creator;

    try {
    testName = root.at("name").get<std::string>();
    
    // Попытка извлечь "creator", если оно отсутствует, будет использовано значение по умолчанию
    if (root.contains("creator")) {
        creator = root.at("creator").get<std::string>();
    } else {
        creator = "unknown_creator"; // Значение по умолчанию
    }

    // Извлечение вопросов из массива объектов
    for (const auto& questionObj : root.at("questions")) {
        std::string questionText = questionObj.at("question").get<std::string>();
        questions.push_back(questionText);
    }
} catch (const json::out_of_range& e) {
    std::cerr << "Ошибка извлечения данных из JSON: " << e.what() << std::endl;
    return 1;
}

    std::cerr << "Название теста: " << testName << std::endl;
    std::cerr << "Создатель: " << creator << std::endl;
    std::cerr << "Вопросы: ";
    for (const auto& q : questions) {
        std::cerr << q << ", ";
    }
    std::cerr << std::endl;

    // Создание базы данных
    DatabaseManager dbManager("tests.db");

    if (!dbManager.createTable()) {
        return 1;
    }

    // Добавление теста в базу данных
    if (!dbManager.insertTest(testName, questions, creator)) {
        return 1;
    }

    std::cout << "Тест успешно обработан." << std::endl;
    return 0;
}
