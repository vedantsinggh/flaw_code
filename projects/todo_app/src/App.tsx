import React from 'react';
import { TodoProvider, useTodos } from './context/TodoContext';
import TodoForm from './components/TodoForm/TodoForm';
import FilterBar from './components/FilterBar/FilterBar';
import TodoList from './components/TodoList/TodoList';
import styles from './App.module.css';

const AppContent: React.FC = () => {
  const { isLoading, error, clearError } = useTodos();

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1>TaskMaster</h1>
      </header>

      {error && (
        <div className={styles.errorMessage}>
          <span>{error}</span>
          <button onClick={clearError} className={styles.closeError}>&times;</button>
        </div>
      )}

      {isLoading ? (
        <div className={styles.loading}>Loading your tasks...</div>
      ) : (
        <>
          <TodoForm />
          <FilterBar />
          <TodoList />
        </>
      )}
    </div>
  );
};

const App: React.FC = () => {
  return (
    <TodoProvider>
      <AppContent />
    </TodoProvider>
  );
};

export default App;