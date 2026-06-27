import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Todo, FilterType } from '../types/todo';
import { todoService } from '../services/api';

interface TodoContextType {
  todos: Todo[];
  isLoading: boolean;
  error: string | null;
  filter: FilterType;
  searchQuery: string;
  addTodo: (text: string) => Promise<void>;
  toggleTodo: (id: string) => Promise<void>;
  deleteTodo: (id: string) => Promise<void>;
  editTodo: (id: string, text: string) => Promise<void>;
  setFilter: (filter: FilterType) => void;
  setSearchQuery: (query: string) => void;
  clearError: () => void;
}

const TodoContext = createContext<TodoContextType | undefined>(undefined);

export const TodoProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadTodos = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await todoService.fetchTodos();
      setTodos(data);
    } catch (err) {
      setError('Failed to load todos.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTodos();
  }, []);

  const addTodo = async (text: string) => {
    try {
      setError(null);
      const newTodo = await todoService.createTodo(text);
      setTodos(prev => [newTodo, ...prev]);
    } catch (err) {
      setError('Failed to create todo.');
    }
  };

  const toggleTodo = async (id: string) => {
    const todo = todos.find(t => t.id === id);
    if (!todo) return;
    
    // Optimistic update
    setTodos(prev => prev.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
    
    try {
      await todoService.updateTodo(id, { completed: !todo.completed });
    } catch (err) {
      // Rollback
      setTodos(prev => prev.map(t => t.id === id ? { ...t, completed: todo.completed } : t));
      setError('Failed to update todo.');
    }
  };

  const deleteTodo = async (id: string) => {
    // Optimistic update
    const previousTodos = [...todos];
    setTodos(prev => prev.filter(t => t.id !== id));

    try {
      await todoService.deleteTodo(id);
    } catch (err) {
      setTodos(previousTodos);
      setError('Failed to delete todo.');
    }
  };

  const editTodo = async (id: string, text: string) => {
    // Optimistic update
    const previousTodos = [...todos];
    setTodos(prev => prev.map(t => t.id === id ? { ...t, text } : t));

    try {
      await todoService.updateTodo(id, { text });
    } catch (err) {
      setTodos(previousTodos);
      setError('Failed to edit todo.');
    }
  };

  const clearError = () => setError(null);

  return (
    <TodoContext.Provider value={{
      todos,
      isLoading,
      error,
      filter,
      searchQuery,
      addTodo,
      toggleTodo,
      deleteTodo,
      editTodo,
      setFilter,
      setSearchQuery,
      clearError
    }}>
      {children}
    </TodoContext.Provider>
  );
};

export const useTodos = () => {
  const context = useContext(TodoContext);
  if (!context) throw new Error('useTodos must be used within a TodoProvider');
  return context;
};