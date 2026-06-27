import { Todo, ApiError } from '../types/todo';

const STORAGE_KEY = 'todo_app_data';
const LATENCY_MS = 300; // Simulate network latency

// Helper to simulate delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Helper to get data from LocalStorage
const getStoredData = (): Todo[] => {
  const data = localStorage.getItem(STORAGE_KEY);
  return data ? JSON.parse(data) : [];
};

// Helper to save data to LocalStorage
const saveStoredData = (todos: Todo[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
};

class TodoService {
  async fetchTodos(): Promise<Todo[]> {
    await delay(LATENCY_MS);
    return getStoredData();
  }

  async createTodo(text: string): Promise<Todo> {
    await delay(LATENCY_MS);
    const todos = getStoredData();
    const newTodo: Todo = {
      id: crypto.randomUUID(),
      text,
      completed: false,
      createdAt: new Date().toISOString(),
    };
    const updatedTodos = [newTodo, ...todos];
    saveStoredData(updatedTodos);
    return newTodo;
  }

  async updateTodo(id: string, updates: Partial<Omit<Todo, 'id' | 'createdAt'>>): Promise<Todo> {
    await delay(LATENCY_MS);
    const todos = getStoredData();
    const index = todos.findIndex(t => t.id === id);
    if (index === -1) throw new Error('Todo not found') as ApiError;
    
    const updatedTodo = { ...todos[index], ...updates };
    const updatedTodos = [...todos];
    updatedTodos[index] = updatedTodo;
    saveStoredData(updatedTodos);
    return updatedTodo;
  }

  async deleteTodo(id: string): Promise<void> {
    await delay(LATENCY_MS);
    let todos = getStoredData();
    todos = todos.filter(t => t.id !== id);
    saveStoredData(todos);
  }
}

export const todoService = new TodoService();