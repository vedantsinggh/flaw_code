import React from 'react';
import { useTodos } from '../../context/TodoContext';
import TodoItem from '../TodoItem/TodoItem';
import styles from './TodoList.module.css';

const TodoList: React.FC = () => {
  const { todos, filter, searchQuery } = useTodos();

  const filteredTodos = todos.filter((todo) => {
    const matchesFilter = 
      filter === 'all' ? true :
      filter === 'active' ? !todo.completed :
      todo.completed;
    
    const matchesSearch = todo.text.toLowerCase().includes(searchQuery.toLowerCase());
    
    return matchesFilter && matchesSearch;
  });

  if (filteredTodos.length === 0) {
    return <div className={styles.emptyState}>No tasks found.</div>;
  }

  return (
    <ul className={styles.list}>
      {filteredTodos.map((todo) => (
        <TodoItem key={todo.id} todo={todo} />
      ))}
    </ul>
  );
};

export default TodoList;