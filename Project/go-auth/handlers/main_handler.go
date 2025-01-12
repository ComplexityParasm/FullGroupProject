package handlers

import (
	"bytes"
	"encoding/json"
	"go-auth/auth"
	"log"
	"net/http"
	"os/exec"

	//"strings"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
)

var redisClient *redis.Client

func SetRedisClient(client *redis.Client) {
	redisClient = client
}

func ProfileHandler(c *gin.Context) {
	// Получаем токен из cookie
	tokenString, err := c.Cookie("Authorization")
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Authorization token missing"})
		return
	}

	// Проверка и парсинг токена
	claims, err := auth.ParseToken(tokenString)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
		return
	}

	// Отображаем информацию о пользователе
	c.HTML(http.StatusOK, "profile.html", gin.H{
		"email": claims.Email,
		"roles": claims.Roles,
	})
}
func SubmitTestHandler(c *gin.Context) {
	var test struct {
		Name      string `json:"name"`
		Questions []struct {
			Question string   `json:"question"`
			Answers  []string `json:"answers"`
		} `json:"questions"`
	}

	if err := c.ShouldBindJSON(&test); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid input"})
		return
	}

	// Сериализация JSON для передачи в C++ модуль
	jsonData, _ := json.Marshal(test)
	log.Printf("Передача данных в C++ модуль: %s", string(jsonData))

	// Передача данных в C++ модуль
	cmd := exec.Command("../../MainModule/main")
	cmd.Stdin = bytes.NewReader(jsonData)
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("Ошибка выполнения C++ модуля: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process test", "details": string(output)})
		return
	}

	log.Printf("C++ Output: %s", output)
	c.JSON(http.StatusOK, gin.H{"message": "Test saved successfully", "output": string(output)})
}
func GetTestsHandler(c *gin.Context) {
	// Пример вызова C++ модуля
	cmd := exec.Command("../../MainModule/main", "fetch")
	output, err := cmd.Output()
	if err != nil {
		log.Printf("Ошибка выполнения C++: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch tests"})
		return
	}

	var tests []struct {
		ID        int    `json:"id"`
		Name      string `json:"name"`
		Creator   string `json:"creator"`
		Questions []struct {
			Question string   `json:"question"`
			Answers  []string `json:"answers"`
		} `json:"questions"`
	}

	if err := json.Unmarshal(output, &tests); err != nil {
		log.Printf("Ошибка парсинга JSON: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse test data"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"tests": tests})
}
func CreateTestHandler(c *gin.Context) {
	var input struct {
		Name      string `json:"name"`
		Questions []struct {
			Question string   `json:"question"`
			Answers  []string `json:"answers"`
		} `json:"questions"`
	}

	if err := c.ShouldBindJSON(&input); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"message": "Invalid input"})
		return
	}

	// Формируем JSON для передачи в C++ модуль
	jsonData, _ := json.Marshal(input)
	log.Printf("Передача данных в C++ модуль: %s", string(jsonData))

	// Запускаем C++ модуль
	cmd := exec.Command("../../MainModule/main")
	cmd.Stdin = bytes.NewReader(jsonData)
	output, err := cmd.CombinedOutput()

	if err != nil {
		log.Printf("Ошибка выполнения C++-модуля: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"message": "Ошибка выполнения C++ модуля", "error": err.Error(), "output": string(output)})
		return
	}

	log.Printf("C++ Output: %s", output)
	c.JSON(http.StatusOK, gin.H{"message": "Тест успешно обработан!", "output": string(output)})
}
